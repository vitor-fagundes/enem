"""Run, aquisições, issues e relatório da ingestão local (SPEC-004)."""

import hashlib
import json
import math
import os
import sqlite3
import threading
import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from enem_rei_ingestion import __version__, ingest
from enem_rei_ingestion.db import (
    IngestionRun,
    SourceResource,
    get_connection,
    get_ingestion_issue_by_id,
    get_ingestion_run_by_id,
    get_resource_acquisition_by_id,
    get_source_resource_by_id,
    insert_source_resource,
)
from enem_rei_ingestion.ingest import (
    DEFAULT_MAX_INPUT_BYTES,
    PIPELINE_NAME,
    RECOVERY_CAUSE,
    OrphanPayloadDivergent,
    ReportUnavailable,
    create_run,
    finalize_run,
    generate_report,
    reconcile_orphan,
    record_acquisition,
    record_issue,
    recover_abandoned_runs,
    revalidate_existing,
)
from enem_rei_ingestion.store import (
    UnsafeStoragePath,
    create_temp_file,
    open_storage_anchor,
    publish_payload,
)

FIXED_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0
    return parsed


def test_create_run_records_running_run(fresh_db: sqlite3.Connection) -> None:
    before = datetime.now(UTC)
    run = create_run(fresh_db, {"opcao": "valor"})
    after = datetime.now(UTC)

    assert str(uuid.UUID(run.id)) == run.id
    assert run.pipeline_name == PIPELINE_NAME == "enem_rei_ingestion"
    assert run.pipeline_version == __version__
    assert run.status == "RUNNING"
    assert run.finished_at is None and run.results is None
    assert before <= parse_utc(run.started_at) <= after
    assert json.loads(run.parameters) == {
        "opcao": "valor",
        "max_input_bytes": DEFAULT_MAX_INPUT_BYTES,
    }
    assert get_ingestion_run_by_id(fresh_db, run.id) == run


def test_create_run_allocates_distinct_ids(fresh_db: sqlite3.Connection) -> None:
    assert create_run(fresh_db, {}).id != create_run(fresh_db, {}).id


def test_default_max_input_bytes_is_finite_positive_int() -> None:
    assert isinstance(DEFAULT_MAX_INPUT_BYTES, int)
    assert 0 < DEFAULT_MAX_INPUT_BYTES < math.inf


@pytest.mark.parametrize("override", [0, 1, 1024])
def test_create_run_records_valid_limit_override(
    fresh_db: sqlite3.Connection, override: int
) -> None:
    run = create_run(fresh_db, {"max_input_bytes": override})
    assert json.loads(run.parameters)["max_input_bytes"] == override


def test_create_run_none_limit_uses_default(fresh_db: sqlite3.Connection) -> None:
    run = create_run(fresh_db, {"max_input_bytes": None})
    assert json.loads(run.parameters)["max_input_bytes"] == DEFAULT_MAX_INPUT_BYTES


@pytest.mark.parametrize("override", [-1, 1.5, math.inf, True, "1024"])
def test_create_run_rejects_invalid_limit_override(
    fresh_db: sqlite3.Connection, override: object
) -> None:
    with pytest.raises(ValueError):
        create_run(fresh_db, {"max_input_bytes": override})
    assert fresh_db.execute("SELECT count(*) FROM ingestion_run").fetchone() == (0,)


@pytest.mark.parametrize("status", ["SUCCESS", "FAILED"])
def test_finalize_run_sets_status_results_and_finished_at(
    fresh_db: sqlite3.Connection, status: str
) -> None:
    run = create_run(fresh_db, {})
    finished = finalize_run(fresh_db, run, status, {"resources_seen": 0})

    assert finished.status == status
    assert parse_utc(finished.finished_at) >= parse_utc(run.started_at)
    assert json.loads(finished.results) == {"resources_seen": 0}
    assert get_ingestion_run_by_id(fresh_db, run.id) == finished


@pytest.mark.parametrize("status", ["RUNNING", "PARTIAL", "DONE", ""])
def test_finalize_run_rejects_unsupported_status(
    fresh_db: sqlite3.Connection, status: str
) -> None:
    run = create_run(fresh_db, {})
    with pytest.raises(ValueError):
        finalize_run(fresh_db, run, status, {})
    assert get_ingestion_run_by_id(fresh_db, run.id) == run


def test_finalize_run_rejects_repeated_finalization(
    fresh_db: sqlite3.Connection,
) -> None:
    run = create_run(fresh_db, {})
    finished = finalize_run(fresh_db, run, "SUCCESS", {})
    with pytest.raises(ValueError):
        finalize_run(fresh_db, finished, "FAILED", {})
    with pytest.raises(ValueError):
        finalize_run(fresh_db, run, "FAILED", {})
    assert get_ingestion_run_by_id(fresh_db, run.id) == finished


def test_run_helpers_do_not_commit(fresh_db: sqlite3.Connection) -> None:
    run = create_run(fresh_db, {})
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert get_ingestion_run_by_id(fresh_db, run.id) is None

    run = create_run(fresh_db, {})
    fresh_db.commit()
    finalize_run(fresh_db, run, "SUCCESS", {})
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert get_ingestion_run_by_id(fresh_db, run.id) == run


def test_create_run_fatal_persistence_failure_reports_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(ingest.uuid, "uuid4", lambda: FIXED_UUID)
    conn = get_connection(tmp_path / "sem_schema.db")
    try:
        with pytest.raises(sqlite3.Error):
            create_run(conn, {})
    finally:
        conn.close()
    stderr = capsys.readouterr().err
    assert "FATAL" in stderr
    assert str(FIXED_UUID) in stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["sem_schema.db"]


def make_resource(
    conn: sqlite3.Connection, resource_id: str = "res-1", fill: str = "a"
) -> SourceResource:
    resource = SourceResource(
        id=resource_id,
        sha256=fill * 64,
        byte_size=3,
        media_type=None,
        storage_locator=f"raw/resources/{fill * 64}/payload",
        registered_at="2026-10-12T00:00:00+00:00",
    )
    insert_source_resource(conn, resource)
    return resource


@pytest.fixture
def run(fresh_db: sqlite3.Connection) -> IngestionRun:
    return create_run(fresh_db, {})


@pytest.fixture
def resource(fresh_db: sqlite3.Connection) -> SourceResource:
    return make_resource(fresh_db)


SOURCE_FIELDS = (
    "source_definition_id",
    "source_url",
    "provider",
    "received_filename",
    "source_retrieved_at",
)


def test_acquisition_local_file_with_complete_metadata(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    before = datetime.now(UTC)
    acquisition = record_acquisition(
        fresh_db,
        resource,
        run,
        "LOCAL_FILE",
        input_path="/entrada/dir/microdados_2023.zip",
        source_definition_id="inep-microdados-enem",
        source_url="https://download.inep.gov.br/microdados_2023.zip",
        provider="INEP",
        source_retrieved_at="2026-01-02T03:04:05Z",
    )
    after = datetime.now(UTC)

    assert str(uuid.UUID(acquisition.id)) == acquisition.id
    assert acquisition.resource_id == resource.id
    assert acquisition.ingestion_run_id == run.id
    assert acquisition.acquisition_method == "LOCAL_FILE"
    assert before <= parse_utc(acquisition.observed_at) <= after
    assert acquisition.received_filename == "microdados_2023.zip"
    assert acquisition.source_definition_id == "inep-microdados-enem"
    assert acquisition.source_url == "https://download.inep.gov.br/microdados_2023.zip"
    assert acquisition.provider == "INEP"
    assert acquisition.source_retrieved_at == "2026-01-02T03:04:05Z"
    assert acquisition.parent_resource_id is None
    assert acquisition.container_locator is None
    assert acquisition.fixture_kind is None
    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) == acquisition


def test_acquisition_local_file_without_metadata_fabricates_nothing(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    acquisition = record_acquisition(fresh_db, resource, run, "LOCAL_FILE")
    for field in SOURCE_FIELDS:
        assert getattr(acquisition, field) is None, field
    assert acquisition.observed_at is not None
    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) == acquisition


@pytest.mark.parametrize(
    ("input_path", "expected"),
    [
        ("arquivo.pdf", "arquivo.pdf"),
        ("/a/b/prova azul.pdf", "prova azul.pdf"),
        (Path("rel/dir/gabarito.csv"), "gabarito.csv"),
    ],
)
def test_acquisition_received_filename_is_basename(
    fresh_db: sqlite3.Connection,
    run: IngestionRun,
    resource: SourceResource,
    input_path: str | Path,
    expected: str,
) -> None:
    acquisition = record_acquisition(
        fresh_db, resource, run, "LOCAL_FILE", input_path=input_path
    )
    assert acquisition.received_filename == expected


def test_acquisition_repeated_observations_keep_all_records(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    first = record_acquisition(fresh_db, resource, run, "LOCAL_FILE")
    second_run = create_run(fresh_db, {})
    second = record_acquisition(
        fresh_db, resource, second_run, "LOCAL_FILE", provider="INEP"
    )
    assert first.id != second.id
    rows = fresh_db.execute(
        "SELECT id FROM resource_acquisition WHERE resource_id = ? ORDER BY id",
        (resource.id,),
    ).fetchall()
    assert sorted(row[0] for row in rows) == sorted([first.id, second.id])
    assert get_resource_acquisition_by_id(fresh_db, first.id) == first


def test_acquisition_container_member(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    member = make_resource(fresh_db, "res-membro", "b")
    acquisition = record_acquisition(
        fresh_db,
        member,
        run,
        "CONTAINER_MEMBER",
        parent_resource_id=resource.id,
        container_locator="DADOS/microdados.csv",
        fixture_kind="SYNTHETIC",
    )
    assert acquisition.parent_resource_id == resource.id
    assert acquisition.container_locator == "DADOS/microdados.csv"
    assert acquisition.fixture_kind == "SYNTHETIC"
    assert acquisition.received_filename is None
    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) == acquisition


def test_acquisition_container_member_requires_parent_and_locator(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        record_acquisition(fresh_db, resource, run, "CONTAINER_MEMBER")


def test_acquisition_fixture(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    acquisition = record_acquisition(
        fresh_db,
        resource,
        run,
        "FIXTURE",
        input_path="fixtures/sintetico.zip",
        fixture_kind="SYNTHETIC",
    )
    assert acquisition.acquisition_method == "FIXTURE"
    assert acquisition.fixture_kind == "SYNTHETIC"
    assert acquisition.received_filename == "sintetico.zip"
    assert acquisition.provider is None and acquisition.source_url is None
    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) == acquisition


def test_acquisition_fixture_requires_fixture_kind(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        record_acquisition(fresh_db, resource, run, "FIXTURE")


@pytest.mark.parametrize(
    "context",
    [
        {"parent_resource_id": "res-1"},
        {"container_locator": "membro.csv"},
        {"fixture_kind": "SYNTHETIC"},
    ],
)
def test_acquisition_local_file_rejects_container_or_fixture_fields(
    fresh_db: sqlite3.Connection,
    run: IngestionRun,
    resource: SourceResource,
    context: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        record_acquisition(fresh_db, resource, run, "LOCAL_FILE", **context)
    assert fresh_db.execute("SELECT count(*) FROM resource_acquisition").fetchone() == (
        0,
    )


def test_acquisition_rejects_invalid_references(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    missing_resource = make_resource(fresh_db, "temp", "c")
    fresh_db.execute("DELETE FROM source_resource WHERE id = 'temp'")
    with pytest.raises(sqlite3.IntegrityError):
        record_acquisition(fresh_db, missing_resource, run, "LOCAL_FILE")

    missing_run = replace(run, id="run-inexistente")
    with pytest.raises(sqlite3.IntegrityError):
        record_acquisition(fresh_db, resource, missing_run, "LOCAL_FILE")

    with pytest.raises(sqlite3.IntegrityError):
        record_acquisition(
            fresh_db,
            resource,
            run,
            "CONTAINER_MEMBER",
            parent_resource_id="inexistente",
            container_locator="membro.csv",
        )


def test_acquisition_participates_in_caller_transaction(
    fresh_db: sqlite3.Connection,
) -> None:
    run = create_run(fresh_db, {})
    fresh_db.commit()
    resource = make_resource(fresh_db)
    acquisition = record_acquisition(fresh_db, resource, run, "LOCAL_FILE")
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) is None
    assert fresh_db.execute("SELECT count(*) FROM source_resource").fetchone() == (0,)
    assert get_ingestion_run_by_id(fresh_db, run.id) == run


def document_locator(resource_id: str) -> dict[str, object]:
    return {"resource_id": resource_id, "locator_type": "DOCUMENT", "locator_value": {}}


def test_issue_without_resource_keeps_input_reference(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    issue = record_issue(
        fresh_db,
        run.id,
        "input_validation",
        "ERROR",
        "entrada não é arquivo regular",
        input_reference="/entrada/fifo",
        exception_type="InputRejected",
    )
    assert str(uuid.UUID(issue.id)) == issue.id
    assert issue.run_id == run.id
    assert issue.resource_id is None and issue.locator is None
    assert issue.input_reference == "/entrada/fifo"
    assert issue.exception_type == "InputRejected"
    assert get_ingestion_issue_by_id(fresh_db, issue.id) == issue


def test_issue_without_optional_fields_fabricates_nothing(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    issue = record_issue(fresh_db, run.id, "preserve", "WARNING", "aviso")
    assert (issue.resource_id, issue.input_reference) == (None, None)
    assert (issue.locator, issue.exception_type) == (None, None)


def test_issue_with_resource_and_matching_locator(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    issue = record_issue(
        fresh_db,
        run.id,
        "revalidation",
        "ERROR",
        "hash divergente",
        resource_id=resource.id,
        locator=document_locator(resource.id),
    )
    assert issue.resource_id == resource.id
    assert json.loads(issue.locator) == document_locator(resource.id)
    assert get_ingestion_issue_by_id(fresh_db, issue.id) == issue


def test_issue_rejects_locator_for_other_resource(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    with pytest.raises(ValueError):
        record_issue(
            fresh_db,
            run.id,
            "revalidation",
            "ERROR",
            "x",
            resource_id=resource.id,
            locator=document_locator("outro"),
        )
    assert fresh_db.execute("SELECT count(*) FROM ingestion_issue").fetchone() == (0,)


@pytest.mark.parametrize(
    "locator", [{"locator_type": "DOCUMENT", "locator_value": {}}, "DOCUMENT"]
)
def test_issue_rejects_locator_without_resource_id(
    fresh_db: sqlite3.Connection, run: IngestionRun, locator: object
) -> None:
    with pytest.raises(ValueError):
        record_issue(fresh_db, run.id, "s", "ERROR", "x", locator=locator)


def test_issue_rejects_invalid_references(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        record_issue(fresh_db, "run-inexistente", "s", "ERROR", "x")
    with pytest.raises(sqlite3.IntegrityError):
        record_issue(fresh_db, run.id, "s", "ERROR", "x", resource_id="inexistente")
    with pytest.raises(sqlite3.IntegrityError):
        record_issue(fresh_db, run.id, "s", "CRITICAL", "x")


def test_issue_does_not_commit(fresh_db: sqlite3.Connection) -> None:
    run = create_run(fresh_db, {})
    fresh_db.commit()
    issue = record_issue(fresh_db, run.id, "s", "INFO", "x")
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert get_ingestion_issue_by_id(fresh_db, issue.id) is None


def unit(name: str, status: str, resource_id: str | None) -> dict[str, object]:
    return {"name": name, "status": status, "resource_id": resource_id}


def test_report_of_successful_run(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    acquisition = record_acquisition(fresh_db, resource, run, "LOCAL_FILE")
    issue = record_issue(fresh_db, run.id, "preserve", "INFO", "novo recurso")
    finished = finalize_run(
        fresh_db,
        run,
        "SUCCESS",
        {
            "resources_seen": 1,
            "resources_created": 1,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [unit("preserve_input", "SUCCESS", resource.id)],
        },
    )

    report = generate_report(fresh_db, finished)

    assert report == {
        "run_id": run.id,
        "status": "SUCCESS",
        "started_at": finished.started_at,
        "finished_at": finished.finished_at,
        "pipeline_name": PIPELINE_NAME,
        "pipeline_version": __version__,
        "parameters": json.loads(finished.parameters),
        "resources_seen": 1,
        "resources_created": 1,
        "resources_reused": 0,
        "resources_failed": 0,
        "records_read": None,
        "records_accepted": None,
        "records_rejected": None,
        "units": [
            {
                "name": "preserve_input",
                "status": "SUCCESS",
                "resource_id": resource.id,
                "sha256": resource.sha256,
                "byte_size": resource.byte_size,
            }
        ],
        "acquisitions": [asdict(acquisition)],
        "issues": [{**asdict(issue), "locator": None}],
        "cause": None,
    }
    json.dumps(report)


def test_report_of_failed_run_without_resource(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    issue = record_issue(
        fresh_db, run.id, "input", "ERROR", "falha", input_reference="x.bin"
    )
    finished = finalize_run(
        fresh_db,
        run,
        "FAILED",
        {
            "resources_seen": 1,
            "resources_created": 0,
            "resources_reused": 0,
            "resources_failed": 1,
            "units": [unit("preserve_input", "FAILED", None)],
        },
    )
    report = generate_report(fresh_db, finished)
    assert report["status"] == "FAILED"
    assert report["units"] == [
        {
            "name": "preserve_input",
            "status": "FAILED",
            "resource_id": None,
            "sha256": None,
            "byte_size": None,
        }
    ]
    assert report["acquisitions"] == []
    assert [i["id"] for i in report["issues"]] == [issue.id]


def test_report_uses_persisted_state_not_caller_object(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    finalize_run(
        fresh_db,
        run,
        "FAILED",
        {
            "resources_seen": 0,
            "resources_created": 0,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [],
        },
    )
    stale = replace(run, status="SUCCESS")
    assert generate_report(fresh_db, stale)["status"] == "FAILED"


def test_report_of_running_run_has_no_inferred_outcomes(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    record_acquisition(fresh_db, resource, run, "LOCAL_FILE")
    report = generate_report(fresh_db, run)
    assert report["status"] == "RUNNING"
    assert report["finished_at"] is None
    for counter in (
        "resources_seen",
        "resources_created",
        "resources_reused",
        "resources_failed",
    ):
        assert report[counter] is None
    assert report["units"] == []
    assert len(report["acquisitions"]) == 1


def test_report_only_includes_records_of_the_run(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    other = create_run(fresh_db, {})
    record_acquisition(fresh_db, resource, other, "LOCAL_FILE")
    record_issue(fresh_db, other.id, "s", "INFO", "outro run")
    report = generate_report(fresh_db, run)
    assert report["acquisitions"] == [] and report["issues"] == []


def test_report_parses_issue_locator(
    fresh_db: sqlite3.Connection, run: IngestionRun, resource: SourceResource
) -> None:
    record_issue(
        fresh_db,
        run.id,
        "s",
        "ERROR",
        "x",
        resource_id=resource.id,
        locator=document_locator(resource.id),
    )
    report = generate_report(fresh_db, run)
    assert report["issues"][0]["locator"] == document_locator(resource.id)


@pytest.mark.parametrize(
    "results",
    [
        {
            "resources_seen": 2,
            "resources_created": 1,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [],
        },
        {"resources_seen": 0, "units": []},
        {
            "resources_seen": -1,
            "resources_created": -1,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [],
        },
        {
            "resources_seen": 0,
            "resources_created": 0,
            "resources_reused": 0,
            "resources_failed": 0,
        },
    ],
)
def test_report_rejects_inconsistent_persisted_results(
    fresh_db: sqlite3.Connection, run: IngestionRun, results: dict[str, object]
) -> None:
    finished = finalize_run(fresh_db, run, "SUCCESS", results)
    with pytest.raises(ReportUnavailable):
        generate_report(fresh_db, finished)


def test_report_rejects_unit_with_unknown_resource(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    finished = finalize_run(
        fresh_db,
        run,
        "SUCCESS",
        {
            "resources_seen": 1,
            "resources_created": 1,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [unit("preserve_input", "SUCCESS", "inexistente")],
        },
    )
    with pytest.raises(ReportUnavailable):
        generate_report(fresh_db, finished)


def test_report_requires_persisted_run(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    fresh_db.rollback()
    with pytest.raises(ReportUnavailable, match=run.id):
        generate_report(fresh_db, run)


PAYLOAD_CONTENT = b"conteudo preservado"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD_CONTENT).hexdigest()


def open_fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


@pytest.fixture
def resources_fd(tmp_data_root: Path):
    fd = open_storage_anchor(tmp_data_root)
    yield fd
    os.close(fd)


@pytest.fixture
def stored_payload(resources_fd: int, tmp_data_root: Path) -> Path:
    tmp_fd, tmp_name = create_temp_file(resources_fd, "run-1")
    try:
        os.write(tmp_fd, PAYLOAD_CONTENT)
    finally:
        os.close(tmp_fd)
    return tmp_data_root / publish_payload(resources_fd, tmp_name, PAYLOAD_SHA)


def test_revalidation_accepts_intact_payload(
    resources_fd: int, stored_payload: Path
) -> None:
    before = open_fd_count()
    assert revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before
    assert stored_payload.read_bytes() == PAYLOAD_CONTENT


def test_revalidation_detects_same_size_corruption(
    resources_fd: int, stored_payload: Path
) -> None:
    corrupted = b"X" + PAYLOAD_CONTENT[1:]
    stored_payload.write_bytes(corrupted)
    before = open_fd_count()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before
    assert stored_payload.read_bytes() == corrupted


@pytest.mark.parametrize(
    "corrupted", [PAYLOAD_CONTENT + b"!", PAYLOAD_CONTENT[:-1], b""]
)
def test_revalidation_detects_different_size_corruption(
    resources_fd: int, stored_payload: Path, corrupted: bytes
) -> None:
    stored_payload.write_bytes(corrupted)
    before = open_fd_count()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before


def test_revalidation_rejects_wrong_expected_size(
    resources_fd: int, stored_payload: Path
) -> None:
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT) - 1)
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT) + 1)


def test_revalidation_missing_payload_or_directory(
    resources_fd: int, tmp_data_root: Path
) -> None:
    before = open_fd_count()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    (tmp_data_root / "raw" / "resources" / PAYLOAD_SHA).mkdir()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before


def test_revalidation_never_follows_payload_symlink(
    resources_fd: int, stored_payload: Path, tmp_path: Path
) -> None:
    intact_copy = tmp_path / "copia_intacta"
    intact_copy.write_bytes(PAYLOAD_CONTENT)
    stored_payload.unlink()
    stored_payload.symlink_to(intact_copy)
    before = open_fd_count()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before


def test_revalidation_rejects_non_regular_payload(
    resources_fd: int, stored_payload: Path
) -> None:
    stored_payload.unlink()
    stored_payload.mkdir()
    before = open_fd_count()
    assert not revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before

    stored_payload.rmdir()
    os.mkfifo(stored_payload)
    outcome: list[object] = []
    thread = threading.Thread(
        target=lambda: outcome.append(
            revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
        ),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "revalidação bloqueou em FIFO"
    assert outcome == [False]


def test_revalidation_rejects_symlinked_sha_directory(
    resources_fd: int, tmp_data_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "fora"
    outside.mkdir()
    (outside / "payload").write_bytes(PAYLOAD_CONTENT)
    (tmp_data_root / "raw" / "resources" / PAYLOAD_SHA).symlink_to(outside)
    before = open_fd_count()
    with pytest.raises(UnsafeStoragePath):
        revalidate_existing(resources_fd, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert open_fd_count() == before


@pytest.mark.parametrize(
    ("sha256_hex", "expected_byte_size"),
    [
        (PAYLOAD_SHA.upper(), 1),
        (PAYLOAD_SHA[:-1], 1),
        ("../" + PAYLOAD_SHA[3:], 1),
        (PAYLOAD_SHA, -1),
        (PAYLOAD_SHA, True),
        (PAYLOAD_SHA, 1.0),
    ],
)
def test_revalidation_rejects_invalid_arguments_before_access(
    sha256_hex: str, expected_byte_size: object
) -> None:
    # Descritor inválido: qualquer acesso ao filesystem falharia com OSError.
    with pytest.raises(ValueError):
        revalidate_existing(-1, sha256_hex, expected_byte_size)


def interrupted_run(conn: sqlite3.Connection) -> IngestionRun:
    """Run registrado e confirmado, mas nunca finalizado (processo interrompido)."""
    run = create_run(conn, {})
    conn.commit()
    return run


def test_recover_finalizes_running_run_as_failed(
    fresh_db: sqlite3.Connection,
) -> None:
    abandoned = interrupted_run(fresh_db)
    before = datetime.now(UTC)
    recovered = recover_abandoned_runs(fresh_db)
    after = datetime.now(UTC)

    assert [run.id for run in recovered] == [abandoned.id]
    persisted = get_ingestion_run_by_id(fresh_db, abandoned.id)
    assert persisted == recovered[0]
    assert persisted.status == "FAILED"
    assert before <= parse_utc(persisted.finished_at) <= after
    assert json.loads(persisted.results) == {"cause": RECOVERY_CAUSE}
    assert RECOVERY_CAUSE == "recovered_after_interruption"
    assert persisted.started_at == abandoned.started_at


def test_recover_skips_current_and_finished_runs(
    fresh_db: sqlite3.Connection,
) -> None:
    finished = finalize_run(
        fresh_db,
        interrupted_run(fresh_db),
        "SUCCESS",
        {
            "resources_seen": 0,
            "resources_created": 0,
            "resources_reused": 0,
            "resources_failed": 0,
            "units": [],
        },
    )
    current = interrupted_run(fresh_db)
    assert recover_abandoned_runs(fresh_db, current_run_id=current.id) == []
    assert get_ingestion_run_by_id(fresh_db, current.id) == current
    assert get_ingestion_run_by_id(fresh_db, finished.id) == finished


def test_recover_is_idempotent(fresh_db: sqlite3.Connection) -> None:
    abandoned = interrupted_run(fresh_db)
    first = recover_abandoned_runs(fresh_db)
    assert recover_abandoned_runs(fresh_db) == []
    assert get_ingestion_run_by_id(fresh_db, abandoned.id) == first[0]


def test_recover_preserves_confirmed_acquisitions_and_resources(
    fresh_db: sqlite3.Connection,
) -> None:
    abandoned = create_run(fresh_db, {})
    resource = make_resource(fresh_db)
    acquisition = record_acquisition(fresh_db, resource, abandoned, "LOCAL_FILE")
    fresh_db.commit()

    recover_abandoned_runs(fresh_db)

    assert get_resource_acquisition_by_id(fresh_db, acquisition.id) == acquisition
    assert fresh_db.execute("SELECT count(*) FROM resource_acquisition").fetchone() == (
        1,
    )
    assert fresh_db.execute("SELECT count(*) FROM source_resource").fetchone() == (1,)


def test_recover_report_has_unknown_counters(fresh_db: sqlite3.Connection) -> None:
    abandoned = create_run(fresh_db, {})
    resource = make_resource(fresh_db)
    record_acquisition(fresh_db, resource, abandoned, "LOCAL_FILE")
    fresh_db.commit()
    (recovered,) = recover_abandoned_runs(fresh_db)

    report = generate_report(fresh_db, recovered)

    assert report["status"] == "FAILED"
    assert report["cause"] == RECOVERY_CAUSE
    assert report["finished_at"] == recovered.finished_at
    for counter in (
        "resources_seen",
        "resources_created",
        "resources_reused",
        "resources_failed",
    ):
        assert report[counter] is None
    assert report["units"] == []
    assert len(report["acquisitions"]) == 1


def test_recover_preserves_available_units(fresh_db: sqlite3.Connection) -> None:
    abandoned = create_run(fresh_db, {})
    resource = make_resource(fresh_db)
    confirmed = {"units": [unit("preserve_input", "SUCCESS", resource.id)]}
    fresh_db.execute(
        "UPDATE ingestion_run SET results = ? WHERE id = ?",
        (json.dumps(confirmed), abandoned.id),
    )
    fresh_db.commit()

    (recovered,) = recover_abandoned_runs(fresh_db)

    assert json.loads(recovered.results) == {**confirmed, "cause": RECOVERY_CAUSE}
    report = generate_report(fresh_db, recovered)
    assert report["units"][0]["sha256"] == resource.sha256
    assert report["resources_seen"] is None


def test_recover_report_stays_strict_for_ordinary_failed_runs(
    fresh_db: sqlite3.Connection, run: IngestionRun
) -> None:
    finished = finalize_run(fresh_db, run, "FAILED", {"units": []})
    with pytest.raises(ReportUnavailable):
        generate_report(fresh_db, finished)


def test_recover_does_not_commit(fresh_db: sqlite3.Connection) -> None:
    abandoned = interrupted_run(fresh_db)
    recover_abandoned_runs(fresh_db)
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert get_ingestion_run_by_id(fresh_db, abandoned.id) == abandoned


def resource_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM source_resource").fetchone()[0]


def test_orphan_recovery_registers_intact_payload_for_current_run(
    fresh_db: sqlite3.Connection,
    run: IngestionRun,
    resources_fd: int,
    stored_payload: Path,
) -> None:
    before = datetime.now(UTC)
    resource, acquisition = reconcile_orphan(
        fresh_db,
        resources_fd,
        run,
        PAYLOAD_SHA,
        len(PAYLOAD_CONTENT),
        input_path="/entrada/arquivo.bin",
    )

    assert get_source_resource_by_id(fresh_db, resource.id) == resource
    assert resource.sha256 == PAYLOAD_SHA
    assert resource.byte_size == len(PAYLOAD_CONTENT)
    assert resource.storage_locator == f"raw/resources/{PAYLOAD_SHA}/payload"
    assert parse_utc(resource.registered_at) >= before
    assert resource.media_type is None

    assert acquisition.ingestion_run_id == run.id
    assert acquisition.resource_id == resource.id
    assert acquisition.received_filename == "arquivo.bin"
    rows = fresh_db.execute(
        "SELECT id FROM resource_acquisition WHERE resource_id = ?", (resource.id,)
    ).fetchall()
    assert rows == [(acquisition.id,)]

    issues = generate_report(fresh_db, run)["issues"]
    assert [(i["stage"], i["severity"], i["resource_id"]) for i in issues] == [
        ("orphan_reconciliation", "INFO", resource.id)
    ]
    assert stored_payload.read_bytes() == PAYLOAD_CONTENT


def test_orphan_recovery_rejects_divergent_payload_without_overwrite(
    fresh_db: sqlite3.Connection,
    run: IngestionRun,
    resources_fd: int,
    stored_payload: Path,
) -> None:
    corrupted = b"X" + PAYLOAD_CONTENT[1:]
    stored_payload.write_bytes(corrupted)
    with pytest.raises(OrphanPayloadDivergent):
        reconcile_orphan(fresh_db, resources_fd, run, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert stored_payload.read_bytes() == corrupted
    assert resource_count(fresh_db) == 0
    assert fresh_db.execute("SELECT count(*) FROM resource_acquisition").fetchone() == (
        0,
    )


def test_orphan_recovery_refuses_payload_already_registered(
    fresh_db: sqlite3.Connection,
    run: IngestionRun,
    resources_fd: int,
    stored_payload: Path,
) -> None:
    insert_source_resource(
        fresh_db,
        SourceResource(
            id="res-registrado",
            sha256=PAYLOAD_SHA,
            byte_size=len(PAYLOAD_CONTENT),
            media_type=None,
            storage_locator=f"raw/resources/{PAYLOAD_SHA}/payload",
            registered_at="2026-10-12T00:00:00+00:00",
        ),
    )
    with pytest.raises(ValueError):
        reconcile_orphan(fresh_db, resources_fd, run, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert resource_count(fresh_db) == 1
    assert fresh_db.execute("SELECT count(*) FROM resource_acquisition").fetchone() == (
        0,
    )


def test_orphan_recovery_rolls_back_with_caller_transaction(
    fresh_db: sqlite3.Connection, resources_fd: int, stored_payload: Path
) -> None:
    run = create_run(fresh_db, {})
    fresh_db.commit()
    reconcile_orphan(fresh_db, resources_fd, run, PAYLOAD_SHA, len(PAYLOAD_CONTENT))
    assert fresh_db.in_transaction
    fresh_db.rollback()
    assert resource_count(fresh_db) == 0
    assert fresh_db.execute("SELECT count(*) FROM ingestion_issue").fetchone() == (0,)
    assert stored_payload.read_bytes() == PAYLOAD_CONTENT
