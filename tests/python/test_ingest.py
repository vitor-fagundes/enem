"""Run, aquisições, issues e relatório da ingestão local (SPEC-004)."""

import errno
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
    RESOURCE_COUNTERS,
    IngestionFatal,
    OrphanPayloadDivergent,
    ReportUnavailable,
    create_run,
    finalize_run,
    generate_report,
    ingest_local_file,
    reconcile_orphan,
    record_acquisition,
    record_issue,
    recover_abandoned_runs,
    revalidate_existing,
)
from enem_rei_ingestion.store import (
    UnsafeStoragePath,
    WriterLockHeld,
    acquire_writer_lock,
    create_temp_file,
    open_storage_anchor,
    publish_payload,
    release_writer_lock,
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


# --- Orquestrador `ingest_local_file` (T-021) ---------------------------------


def ingest_file(data_root: Path, path: Path, **options: object) -> dict:
    return ingest_local_file(data_root / "ingestion.db", data_root, path, **options)


def db_rows(data_root: Path, sql: str, params: tuple = ()) -> list[tuple]:
    conn = get_connection(data_root / "ingestion.db")
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def stored_report(data_root: Path, run_id: str) -> dict:
    conn = get_connection(data_root / "ingestion.db")
    try:
        return generate_report(conn, get_ingestion_run_by_id(conn, run_id))
    finally:
        conn.close()


def resource_entries(data_root: Path) -> list[str]:
    return sorted(os.listdir(data_root / "raw" / "resources"))


def counters_of(report: dict) -> tuple[int, int, int, int]:
    return (
        report["resources_seen"],
        report["resources_created"],
        report["resources_reused"],
        report["resources_failed"],
    )


def test_ingest_new_file_publishes_registers_and_reports(
    tmp_data_root: Path, synthetic_file
) -> None:
    content = b"arquivo local novo"
    path, sha = synthetic_file(content, "prova.csv")
    before_fds = open_fd_count()

    report = ingest_file(
        tmp_data_root, path, source_definition_id="DS-003", provider="INEP"
    )

    assert open_fd_count() == before_fds
    assert report["status"] == "SUCCESS"
    assert counters_of(report) == (1, 1, 0, 0)
    assert report["parameters"]["max_input_bytes"] == DEFAULT_MAX_INPUT_BYTES
    [unit_result] = report["units"]
    assert unit_result["name"] == "preserve_input"
    assert unit_result["status"] == "SUCCESS"
    assert (unit_result["sha256"], unit_result["byte_size"]) == (sha, len(content))
    [(locator, media_type)] = db_rows(
        tmp_data_root,
        "SELECT storage_locator, media_type FROM source_resource WHERE id = ?",
        (unit_result["resource_id"],),
    )
    assert locator == f"raw/resources/{sha}/payload"
    assert media_type is None
    assert (tmp_data_root / locator).read_bytes() == content
    [acquisition] = report["acquisitions"]
    assert acquisition["acquisition_method"] == "LOCAL_FILE"
    assert acquisition["received_filename"] == "prova.csv"
    assert acquisition["source_definition_id"] == "DS-003"
    assert acquisition["provider"] == "INEP"
    assert acquisition["source_url"] is None
    assert acquisition["source_retrieved_at"] is None
    assert report["issues"] == []
    assert resource_entries(tmp_data_root) == [sha]
    assert report == stored_report(tmp_data_root, report["run_id"])
    assert db_rows(tmp_data_root, "SELECT id, status FROM ingestion_run") == [
        (report["run_id"], "SUCCESS")
    ]


def test_ingest_same_bytes_reuses_after_revalidation(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, sha = synthetic_file(b"mesmo conteudo")
    first = ingest_file(tmp_data_root, path, source_url="https://a.example/x")
    [(registered_at,)] = db_rows(
        tmp_data_root, "SELECT registered_at FROM source_resource"
    )

    checked = []
    original = ingest.revalidate_existing
    monkeypatch.setattr(
        ingest,
        "revalidate_existing",
        lambda *args: checked.append(args[1:]) or original(*args),
    )
    second = ingest_file(tmp_data_root, path, source_url="https://b.example/y")

    assert checked == [(sha, len(b"mesmo conteudo"))]
    assert second["status"] == "SUCCESS"
    assert counters_of(second) == (1, 0, 1, 0)
    assert second["run_id"] != first["run_id"]
    assert second["units"][0]["resource_id"] == first["units"][0]["resource_id"]
    assert db_rows(tmp_data_root, "SELECT registered_at FROM source_resource") == [
        (registered_at,)
    ]
    urls = db_rows(
        tmp_data_root, "SELECT source_url FROM resource_acquisition ORDER BY rowid"
    )
    assert urls == [("https://a.example/x",), ("https://b.example/y",)]
    assert resource_entries(tmp_data_root) == [sha]


def test_ingest_divergent_payload_fails_without_overwrite(
    tmp_data_root: Path, synthetic_file
) -> None:
    content = b"conteudo original"
    path, sha = synthetic_file(content)
    first = ingest_file(tmp_data_root, path)
    payload = tmp_data_root / "raw" / "resources" / sha / "payload"
    corrupted = b"X" + content[1:]
    payload.write_bytes(corrupted)

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"][0]["status"] == "FAILED"
    assert report["acquisitions"] == []
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("dedup", "ERROR")
    assert issue["resource_id"] == first["units"][0]["resource_id"]
    assert payload.read_bytes() == corrupted
    assert db_rows(tmp_data_root, "SELECT sha256, byte_size FROM source_resource") == [
        (sha, len(content))
    ]
    assert len(db_rows(tmp_data_root, "SELECT id FROM resource_acquisition")) == 1
    assert resource_entries(tmp_data_root) == [sha]


def test_ingest_missing_input_records_failed_run(
    tmp_data_root: Path, tmp_path: Path
) -> None:
    missing = tmp_path / "nao_existe.bin"

    report = ingest_file(tmp_data_root, missing)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == [
        {
            "name": "preserve_input",
            "status": "FAILED",
            "resource_id": None,
            "sha256": None,
            "byte_size": None,
        }
    ]
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("input", "ERROR")
    assert issue["resource_id"] is None
    assert issue["input_reference"] == str(missing)
    assert issue["exception_type"] == "FileNotFoundError"
    assert report["acquisitions"] == []
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM ingestion_run") == [(1,)]
    assert report == stored_report(tmp_data_root, report["run_id"])


def test_ingest_rejected_input_records_failed_run(
    tmp_data_root: Path, synthetic_file
) -> None:
    target, _ = synthetic_file(b"alvo")
    link = target.with_name("link.bin")
    link.symlink_to(target)
    report = ingest_file(tmp_data_root, link)
    assert report["status"] == "FAILED"
    assert report["issues"][0]["exception_type"] == "InputRejected"
    assert resource_entries(tmp_data_root) == []


def test_ingest_limit_exceeded_publishes_nothing(
    tmp_data_root: Path, synthetic_file
) -> None:
    path, _ = synthetic_file(b"12345")

    report = ingest_file(tmp_data_root, path, max_input_bytes=4)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["parameters"]["max_input_bytes"] == 4
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("preserve", "ERROR")
    assert issue["exception_type"] == "SizeLimitExceeded"
    assert resource_entries(tmp_data_root) == []
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]


def test_ingest_exactly_at_limit_succeeds(tmp_data_root: Path, synthetic_file) -> None:
    path, sha = synthetic_file(b"1234")
    report = ingest_file(tmp_data_root, path, max_input_bytes=4)
    assert report["status"] == "SUCCESS"
    assert resource_entries(tmp_data_root) == [sha]


@pytest.mark.parametrize("override", [-1, 1.5, math.inf, True, "1024"])
def test_ingest_invalid_limit_records_failed_run(
    tmp_data_root: Path, synthetic_file, override: object
) -> None:
    path, _ = synthetic_file(b"nao deve ser lido")

    report = ingest_file(tmp_data_root, path, max_input_bytes=override)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (0, 0, 0, 0)
    assert report["parameters"]["max_input_bytes"] is None
    assert report["parameters"]["rejected_parameters"] == {
        "max_input_bytes": repr(override)
    }
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("parameters", "ERROR")
    assert issue["input_reference"] == str(path)
    assert report["acquisitions"] == []
    assert resource_entries(tmp_data_root) == []
    assert db_rows(tmp_data_root, "SELECT count(*) FROM ingestion_run") == [(1,)]


def test_ingest_invalid_fixture_kind_records_failed_run(
    tmp_data_root: Path, synthetic_file
) -> None:
    path, _ = synthetic_file(b"x")
    report = ingest_file(tmp_data_root, path, fixture_kind="REAL")
    assert report["status"] == "FAILED"
    assert report["parameters"]["rejected_parameters"] == {"fixture_kind": "'REAL'"}
    assert report["parameters"]["max_input_bytes"] == DEFAULT_MAX_INPUT_BYTES
    assert resource_entries(tmp_data_root) == []


def test_ingest_fixture_kind_uses_fixture_method(
    tmp_data_root: Path, synthetic_file
) -> None:
    path, _ = synthetic_file(b"fixture sintetica")
    report = ingest_file(tmp_data_root, path, fixture_kind="SYNTHETIC")
    [acquisition] = report["acquisitions"]
    assert acquisition["acquisition_method"] == "FIXTURE"
    assert acquisition["fixture_kind"] == "SYNTHETIC"
    assert report["parameters"]["fixture_kind"] == "SYNTHETIC"


def test_ingest_recovers_abandoned_runs_but_not_current(
    tmp_data_root: Path, fresh_db: sqlite3.Connection, synthetic_file
) -> None:
    abandoned = create_run(fresh_db, {})
    fresh_db.commit()
    path, _ = synthetic_file(b"apos interrupcao")

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "SUCCESS"
    recovered = get_ingestion_run_by_id(fresh_db, abandoned.id)
    assert recovered.status == "FAILED"
    assert json.loads(recovered.results)["cause"] == RECOVERY_CAUSE
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("recovery", "INFO")
    ]
    assert abandoned.id in report["issues"][0]["message"]


def test_ingest_cleans_abandoned_temps_and_leaves_none(
    tmp_data_root: Path, synthetic_file
) -> None:
    resources = tmp_data_root / "raw" / "resources"
    stale = resources / ".tmp.run-antigo.abcd"
    stale.write_bytes(b"parcial")
    path, sha = synthetic_file(b"novo")

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "SUCCESS"
    assert resource_entries(tmp_data_root) == [sha]
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("temp_cleanup", "INFO")
    assert stale.name in issue["message"]


def test_ingest_failure_paths_leave_no_temp(
    tmp_data_root: Path, synthetic_file
) -> None:
    path, _ = synthetic_file(b"grande demais")
    ingest_file(tmp_data_root, path, max_input_bytes=1)
    assert not [n for n in resource_entries(tmp_data_root) if n.startswith(".tmp.")]


def test_ingest_reconciles_orphan_payload(
    tmp_data_root: Path, resources_fd: int, stored_payload: Path, synthetic_file
) -> None:
    path, sha = synthetic_file(PAYLOAD_CONTENT)
    assert sha == PAYLOAD_SHA

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "SUCCESS"
    assert counters_of(report) == (1, 1, 0, 0)
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("orphan_reconciliation", "INFO")
    ]
    assert len(report["acquisitions"]) == 1
    assert stored_payload.read_bytes() == PAYLOAD_CONTENT


def test_ingest_divergent_orphan_fails_without_overwrite(
    tmp_data_root: Path, resources_fd: int, stored_payload: Path, synthetic_file
) -> None:
    corrupted = b"X" + PAYLOAD_CONTENT[1:]
    stored_payload.write_bytes(corrupted)
    path, _ = synthetic_file(PAYLOAD_CONTENT)

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("orphan_reconciliation", "ERROR")
    ]
    assert stored_payload.read_bytes() == corrupted
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert not [n for n in resource_entries(tmp_data_root) if n.startswith(".tmp.")]


def test_ingest_lock_held_is_fatal_without_run(
    tmp_data_root: Path, synthetic_file, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = synthetic_file(b"bloqueado")
    lock_fd = acquire_writer_lock(tmp_data_root)
    try:
        with pytest.raises(IngestionFatal) as raised:
            ingest_file(tmp_data_root, path)
    finally:
        release_writer_lock(lock_fd)
    assert raised.value.run_id is None
    assert "FATAL" in capsys.readouterr().err
    assert not (tmp_data_root / "ingestion.db").exists()
    assert resource_entries(tmp_data_root) == []


def test_ingest_releases_lock_after_each_run(
    tmp_data_root: Path, synthetic_file, tmp_path: Path
) -> None:
    path, _ = synthetic_file(b"a")
    ingest_file(tmp_data_root, path)
    ingest_file(tmp_data_root, tmp_path / "ausente")
    release_writer_lock(acquire_writer_lock(tmp_data_root))


def test_ingest_unavailable_database_is_fatal(
    tmp_data_root: Path, synthetic_file, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = synthetic_file(b"sem banco")
    db_dir = tmp_data_root / "banco_e_diretorio"
    db_dir.mkdir()
    with pytest.raises(IngestionFatal):
        ingest_local_file(db_dir, tmp_data_root, path)
    assert "FATAL" in capsys.readouterr().err
    assert resource_entries(tmp_data_root) == []
    release_writer_lock(acquire_writer_lock(tmp_data_root))


def test_ingest_run_registration_failure_is_fatal_with_run_id(
    tmp_data_root: Path,
    synthetic_file,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path, _ = synthetic_file(b"sem run")
    monkeypatch.setattr(ingest.uuid, "uuid4", lambda: FIXED_UUID)

    def broken_insert(conn, run):
        raise sqlite3.OperationalError("disco cheio simulado")

    monkeypatch.setattr(ingest, "insert_ingestion_run", broken_insert)
    with pytest.raises(IngestionFatal):
        ingest_file(tmp_data_root, path)
    assert str(FIXED_UUID) in capsys.readouterr().err
    assert db_rows(tmp_data_root, "SELECT count(*) FROM ingestion_run") == [(0,)]
    assert resource_entries(tmp_data_root) == []


def test_ingest_persistence_failure_after_publication_fails_run(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, sha = synthetic_file(b"janela entre link e commit")

    def broken_insert(conn, resource):
        raise sqlite3.OperationalError("falha simulada")

    monkeypatch.setattr(ingest, "insert_source_resource", broken_insert)
    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("persistence", "FATAL")
    ]
    # Payload publicado sem linha em SQLite: órfão recuperável (FR-017).
    assert resource_entries(tmp_data_root) == [sha]
    monkeypatch.undo()
    retry = ingest_file(tmp_data_root, path)
    assert retry["status"] == "SUCCESS"
    assert [i["stage"] for i in retry["issues"]] == ["orphan_reconciliation"]


def test_ingest_report_matches_sqlite_for_each_outcome(
    tmp_data_root: Path, synthetic_file, tmp_path: Path
) -> None:
    path, _ = synthetic_file(b"consistencia")
    reports = [
        ingest_file(tmp_data_root, path),
        ingest_file(tmp_data_root, path),
        ingest_file(tmp_data_root, tmp_path / "ausente"),
    ]
    for report in reports:
        assert report == stored_report(tmp_data_root, report["run_id"])
        seen, *outcomes = counters_of(report)
        assert seen == sum(outcomes) == 1
    assert len({r["run_id"] for r in reports}) == 3
    assert db_rows(tmp_data_root, "SELECT count(*) FROM ingestion_run") == [(3,)]


# --- Aceite SPEC-004: casos A, B, C, D, G, O, Q, R (T-022) ---------------------


class SimulatedCrash(BaseException):
    """Interrupção abrupta do processo: não é tratada pelo orquestrador."""


def run_results(data_root: Path, run_id: str) -> dict:
    [(results,)] = db_rows(
        data_root, "SELECT results FROM ingestion_run WHERE id = ?", (run_id,)
    )
    return json.loads(results)


def assert_consistent_run(data_root: Path, report: dict) -> None:
    """Relatório, SQLite e filesystem concordam após o fim do run."""
    assert report == stored_report(data_root, report["run_id"])
    persisted = run_results(data_root, report["run_id"])
    assert counters_of(report) == tuple(persisted[k] for k in RESOURCE_COUNTERS)
    seen, *outcomes = counters_of(report)
    assert seen == sum(outcomes)
    assert report["records_read"] is None
    run_acquisitions = db_rows(
        data_root,
        "SELECT resource_id FROM resource_acquisition WHERE ingestion_run_id = ?",
        (report["run_id"],),
    )
    succeeded = [u["resource_id"] for u in report["units"] if u["status"] == "SUCCESS"]
    # Uma aquisição por unidade concluída; nenhuma para unidade falha.
    assert sorted(r for (r,) in run_acquisitions) == sorted(succeeded)
    assert report["resources_created"] + report["resources_reused"] == len(succeeded)
    # Nenhum recurso registrado sem aquisição; recurso usado tem payload íntegro.
    for resource_id, sha, size, locator in db_rows(
        data_root, "SELECT id, sha256, byte_size, storage_locator FROM source_resource"
    ):
        [(acquisitions,)] = db_rows(
            data_root,
            "SELECT count(*) FROM resource_acquisition WHERE resource_id = ?",
            (resource_id,),
        )
        assert acquisitions >= 1
        if resource_id in succeeded:
            payload = (data_root / locator).read_bytes()
            assert (hashlib.sha256(payload).hexdigest(), len(payload)) == (sha, size)
    assert not [n for n in resource_entries(data_root) if n.startswith(".tmp.")]


def failed_unit() -> list[dict[str, object]]:
    return [
        {
            "name": "preserve_input",
            "status": "FAILED",
            "resource_id": None,
            "sha256": None,
            "byte_size": None,
        }
    ]


def resource_rows(data_root: Path) -> list[tuple]:
    return db_rows(
        data_root,
        "SELECT id, sha256, byte_size, media_type, storage_locator, registered_at"
        " FROM source_resource ORDER BY rowid",
    )


@pytest.mark.parametrize(
    "content", [b"arquivo local novo", b""], ids=["bytes", "empty"]
)
def test_acceptance_case_a_new_local_file(
    tmp_data_root: Path, synthetic_file, content: bytes
) -> None:
    path, sha = synthetic_file(content, "entrada.bin")

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "SUCCESS"
    assert counters_of(report) == (1, 1, 0, 0)
    assert report["pipeline_name"] == PIPELINE_NAME
    assert report["pipeline_version"] == __version__
    assert report["parameters"]["max_input_bytes"] == DEFAULT_MAX_INPUT_BYTES
    assert parse_utc(report["started_at"]) <= parse_utc(report["finished_at"])
    [(resource_id, stored_sha, size, media_type, locator, registered_at)] = (
        resource_rows(tmp_data_root)
    )
    assert (stored_sha, size, media_type) == (sha, len(content), None)
    assert locator == f"raw/resources/{sha}/payload"
    parse_utc(registered_at)
    assert report["units"] == [
        {
            "name": "preserve_input",
            "status": "SUCCESS",
            "resource_id": resource_id,
            "sha256": sha,
            "byte_size": len(content),
        }
    ]
    [acquisition] = report["acquisitions"]
    assert acquisition["resource_id"] == resource_id
    assert acquisition["ingestion_run_id"] == report["run_id"]
    assert acquisition["acquisition_method"] == "LOCAL_FILE"
    assert acquisition["received_filename"] == "entrada.bin"
    parse_utc(acquisition["observed_at"])
    # Origem desconhecida permanece nula; nada é fabricado (FR-004).
    for field_name in (
        "source_definition_id",
        "source_url",
        "provider",
        "source_retrieved_at",
        "parent_resource_id",
        "container_locator",
        "fixture_kind",
    ):
        assert acquisition[field_name] is None
    assert report["issues"] == []
    # Payload é cópia regular independente da origem (FR-006).
    payload = tmp_data_root / locator
    assert payload.read_bytes() == content
    assert payload.stat().st_nlink == 1
    assert payload.stat().st_ino != path.stat().st_ino
    path.write_bytes(b"origem alterada depois")
    assert payload.read_bytes() == content
    assert resource_entries(tmp_data_root) == [sha]
    assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_b_reingestion_reuses_validated_resource(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"mesmos bytes reingeridos"
    path, sha = synthetic_file(content)
    verifications = []
    original_verify = ingest.stream_verify_hash

    def counting_verify(*args, **kwargs):
        verifications.append(args)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(ingest, "stream_verify_hash", counting_verify)

    first = ingest_file(tmp_data_root, path)
    first_verifications = len(verifications)
    payload = tmp_data_root / "raw" / "resources" / sha / "payload"
    before = payload.stat()
    resources_before = resource_rows(tmp_data_root)
    second = ingest_file(tmp_data_root, path)

    # 1ª: só o temporário; 2ª: temporário + revalidação do payload existente.
    assert first_verifications == 1
    assert len(verifications) - first_verifications == 2
    assert (first["status"], second["status"]) == ("SUCCESS", "SUCCESS")
    assert counters_of(first) == (1, 1, 0, 0)
    assert counters_of(second) == (1, 0, 1, 0)
    assert first["run_id"] != second["run_id"]
    assert parse_utc(second["started_at"]) >= parse_utc(first["finished_at"])
    assert second["units"][0]["resource_id"] == first["units"][0]["resource_id"]
    assert second["units"][0]["sha256"] == sha
    assert resource_rows(tmp_data_root) == resources_before
    after = payload.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert payload.read_bytes() == content
    acquisitions = db_rows(
        tmp_data_root,
        "SELECT ingestion_run_id, resource_id FROM resource_acquisition ORDER BY rowid",
    )
    resource_id = first["units"][0]["resource_id"]
    assert acquisitions == [
        (first["run_id"], resource_id),
        (second["run_id"], resource_id),
    ]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM ingestion_run") == [(2,)]
    assert resource_entries(tmp_data_root) == [sha]
    for report in (first, second):
        assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_c_same_path_new_content_is_new_resource(
    tmp_data_root: Path, synthetic_file
) -> None:
    v1 = b"versao 1"
    path, sha1 = synthetic_file(v1, "mesmo_nome.csv")
    url = "https://fonte.example/mesmo_nome.csv"
    first = ingest_file(tmp_data_root, path, source_url=url)
    [v1_row] = resource_rows(tmp_data_root)
    v2 = b"versao 2 com bytes diferentes"
    path.write_bytes(v2)
    sha2 = hashlib.sha256(v2).hexdigest()

    second = ingest_file(tmp_data_root, path, source_url=url)

    assert counters_of(first) == counters_of(second) == (1, 1, 0, 0)
    rows = resource_rows(tmp_data_root)
    assert rows[0] == v1_row
    assert [(row[1], row[2]) for row in rows] == [(sha1, len(v1)), (sha2, len(v2))]
    assert first["units"][0]["resource_id"] != second["units"][0]["resource_id"]
    assert resource_entries(tmp_data_root) == sorted([sha1, sha2])
    resources = tmp_data_root / "raw" / "resources"
    assert (resources / sha1 / "payload").read_bytes() == v1
    assert (resources / sha2 / "payload").read_bytes() == v2
    # Mesmo caminho/URL não cria supersessão: cada aquisição aponta seu recurso.
    assert db_rows(
        tmp_data_root,
        "SELECT resource_id, source_url, received_filename"
        " FROM resource_acquisition ORDER BY rowid",
    ) == [
        (first["units"][0]["resource_id"], url, "mesmo_nome.csv"),
        (second["units"][0]["resource_id"], url, "mesmo_nome.csv"),
    ]
    assert second["issues"] == []
    for report in (first, second):
        assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_d_same_bytes_from_different_origins(
    tmp_data_root: Path, synthetic_file
) -> None:
    content = b"bytes identicos de origens distintas"
    origins = [
        ("dados_2023.csv", {"source_definition_id": "DS-003", "provider": "INEP"}),
        (
            "copia.csv",
            {
                "source_url": "https://espelho.example/copia.csv",
                "source_retrieved_at": "2026-01-02T03:04:05+00:00",
            },
        ),
        ("sem_contexto.bin", {}),
    ]
    reports = []
    for name, options in origins:
        path, sha = synthetic_file(content, name)
        reports.append(ingest_file(tmp_data_root, path, **options))
        if len(reports) == 1:
            first_resource = resource_rows(tmp_data_root)

    assert [counters_of(r) for r in reports] == [
        (1, 1, 0, 0),
        (1, 0, 1, 0),
        (1, 0, 1, 0),
    ]
    # Metadados intrínsecos não mudam com novas origens.
    assert resource_rows(tmp_data_root) == first_resource
    [(resource_id, *_)] = first_resource
    rows = db_rows(
        tmp_data_root,
        "SELECT resource_id, ingestion_run_id, received_filename,"
        " source_definition_id, provider, source_url, source_retrieved_at"
        " FROM resource_acquisition ORDER BY rowid",
    )
    assert rows == [
        (resource_id, reports[0]["run_id"], "dados_2023.csv", "DS-003", "INEP")
        + (None, None),
        (resource_id, reports[1]["run_id"], "copia.csv", None, None)
        + ("https://espelho.example/copia.csv", "2026-01-02T03:04:05+00:00"),
        (resource_id, reports[2]["run_id"], "sem_contexto.bin", None, None)
        + (None, None),
    ]
    assert resource_entries(tmp_data_root) == [sha]
    for report in reports:
        assert_consistent_run(tmp_data_root, report)


@pytest.mark.parametrize(
    "corrupt",
    [
        pytest.param(lambda data: b"X" + data[1:], id="same_size"),
        pytest.param(lambda data: data + b"!", id="larger"),
        pytest.param(lambda data: data[:-3], id="truncated"),
        pytest.param(None, id="missing"),
    ],
)
def test_acceptance_case_g_corrupted_payload_fails_explicitly(
    tmp_data_root: Path, synthetic_file, corrupt
) -> None:
    content = b"conteudo registrado com hash AAA"
    path, sha = synthetic_file(content)
    first = ingest_file(tmp_data_root, path)
    resources_before = resource_rows(tmp_data_root)
    payload = tmp_data_root / "raw" / "resources" / sha / "payload"
    if corrupt is None:
        payload.unlink()
        damaged = None
    else:
        damaged = corrupt(content)
        payload.write_bytes(damaged)

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == failed_unit()
    assert report["acquisitions"] == []
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("dedup", "ERROR")
    assert issue["resource_id"] == first["units"][0]["resource_id"]
    # Sem correção de manifesto, sem sobrescrita/republicação do payload.
    assert resource_rows(tmp_data_root) == resources_before
    if damaged is None:
        assert not payload.exists()
    else:
        assert payload.read_bytes() == damaged
    assert db_rows(
        tmp_data_root, "SELECT ingestion_run_id FROM resource_acquisition"
    ) == [(first["run_id"],)]
    assert_consistent_run(tmp_data_root, report)


def make_missing(tmp_path: Path) -> Path:
    return tmp_path / "nao_existe.bin"


def make_directory(tmp_path: Path) -> Path:
    path = tmp_path / "diretorio"
    path.mkdir()
    return path


def make_symlink(tmp_path: Path) -> Path:
    target = tmp_path / "alvo.bin"
    target.write_bytes(b"alvo")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    return link


def make_fifo(tmp_path: Path) -> Path:
    path = tmp_path / "fifo"
    os.mkfifo(path)
    return path


@pytest.mark.parametrize(
    ("make_input", "exception_type"),
    [
        (make_missing, "FileNotFoundError"),
        (make_directory, "InputRejected"),
        (make_symlink, "InputRejected"),
        (make_fifo, "InputRejected"),
    ],
)
def test_acceptance_case_o_invalid_input_fails_without_fabrication(
    tmp_data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_input,
    exception_type: str,
) -> None:
    bad_input = make_input(tmp_path)
    observed = []
    original_open = ingest.open_validated_input

    def checking_open(path):
        # Validação ocorre com o lock retido e o run já confirmado em SQLite.
        with pytest.raises(WriterLockHeld):
            acquire_writer_lock(tmp_data_root)
        observed.append(db_rows(tmp_data_root, "SELECT status FROM ingestion_run"))
        return original_open(path)

    monkeypatch.setattr(ingest, "open_validated_input", checking_open)

    report = ingest_file(tmp_data_root, bad_input)

    assert observed == [[("RUNNING",)]]
    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == failed_unit()
    [issue] = report["issues"]
    assert (issue["stage"], issue["severity"]) == ("input", "ERROR")
    assert issue["resource_id"] is None
    assert issue["input_reference"] == str(bad_input)
    assert issue["exception_type"] == exception_type
    assert report["acquisitions"] == []
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM resource_acquisition") == [(0,)]
    assert db_rows(tmp_data_root, "SELECT id, status FROM ingestion_run") == [
        (report["run_id"], "FAILED")
    ]
    assert resource_entries(tmp_data_root) == []
    assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_o_sqlite_failure_is_fatal_without_feigned_persistence(
    tmp_data_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    synthetic_file,
) -> None:
    def broken_finalize(*args, **kwargs):
        raise sqlite3.OperationalError("banco indisponível simulado")

    monkeypatch.setattr(ingest, "finalize_run", broken_finalize)
    with pytest.raises(IngestionFatal) as raised:
        ingest_file(tmp_data_root, make_missing(tmp_path))

    run_id = raised.value.run_id
    assert run_id is not None
    assert f"FATAL (run {run_id})" in capsys.readouterr().err
    # Nada foi declarado persistido: o run segue RUNNING, sem resultados.
    assert db_rows(tmp_data_root, "SELECT id, status, results FROM ingestion_run") == [
        (run_id, "RUNNING", None)
    ]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert resource_entries(tmp_data_root) == []
    monkeypatch.undo()
    path, _ = synthetic_file(b"proxima execucao")
    report = ingest_file(tmp_data_root, path)
    assert report["status"] == "SUCCESS"
    assert stored_report(tmp_data_root, run_id)["status"] == "FAILED"
    assert run_results(tmp_data_root, run_id) == {"cause": RECOVERY_CAUSE}


def test_acceptance_case_q_origin_changed_during_read(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = b"A" * 65536 + b"B" * 65536
    path, original_sha = synthetic_file(original)
    delivered = []
    original_copy = ingest.stream_copy_hash

    class MutatingSource:
        def __init__(self, source) -> None:
            self.source = source

        def read(self, size: int) -> bytes:
            chunk = self.source.read(size)
            if not delivered:
                # Outro processo reescreve o restante da origem durante a cópia.
                with path.open("r+b") as handle:
                    handle.seek(65536)
                    handle.write(b"C" * 65536)
            delivered.append(chunk)
            return chunk

    monkeypatch.setattr(
        ingest,
        "stream_copy_hash",
        lambda src, dst, max_bytes: original_copy(MutatingSource(src), dst, max_bytes),
    )

    report = ingest_file(tmp_data_root, path)

    copied = b"".join(delivered)
    assert copied != original  # A mudança foi observada pela cópia.
    copied_sha = hashlib.sha256(copied).hexdigest()
    assert report["status"] == "SUCCESS"
    [unit_result] = report["units"]
    # Hash anunciado = bytes efetivamente copiados, nunca a leitura anterior.
    assert (unit_result["sha256"], unit_result["byte_size"]) == (
        copied_sha,
        len(copied),
    )
    assert unit_result["sha256"] != original_sha
    payload = tmp_data_root / "raw" / "resources" / copied_sha / "payload"
    assert payload.read_bytes() == copied
    assert resource_entries(tmp_data_root) == [copied_sha]
    path.write_bytes(b"alterada de novo depois da ingestao")
    assert payload.read_bytes() == copied
    assert_consistent_run(tmp_data_root, report)


def crash_between_publication_and_commit(
    tmp_data_root: Path, path: Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Simula queda após `os.link` e antes do commit; devolve o run abandonado."""

    def crash(conn, resource):
        raise SimulatedCrash

    with monkeypatch.context() as patch:
        patch.setattr(ingest, "insert_source_resource", crash)
        with pytest.raises(SimulatedCrash):
            ingest_file(tmp_data_root, path)
    [(run_id, status)] = db_rows(tmp_data_root, "SELECT id, status FROM ingestion_run")
    assert status == "RUNNING"
    return run_id


def test_acceptance_case_r_crash_after_publication_then_reconcile(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"publicado antes do commit"
    path, sha = synthetic_file(content)

    crashed_run = crash_between_publication_and_commit(tmp_data_root, path, monkeypatch)

    # Órfão: payload final sem linha em SQLite, detectável e não registrado.
    assert resource_entries(tmp_data_root) == [sha]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM resource_acquisition") == [(0,)]
    abandoned = stored_report(tmp_data_root, crashed_run)
    assert abandoned["status"] == "RUNNING"
    assert abandoned["resources_seen"] is None

    report = ingest_file(tmp_data_root, path, source_url="https://nova.example/x")

    assert report["status"] == "SUCCESS"
    assert counters_of(report) == (1, 1, 0, 0)
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("recovery", "INFO"),
        ("orphan_reconciliation", "INFO"),
    ]
    assert crashed_run in report["issues"][0]["message"]
    # Só a aquisição da execução atual; nenhuma aquisição passada inventada.
    [acquisition] = report["acquisitions"]
    assert acquisition["ingestion_run_id"] == report["run_id"]
    assert acquisition["source_url"] == "https://nova.example/x"
    assert db_rows(
        tmp_data_root,
        "SELECT count(*) FROM resource_acquisition WHERE ingestion_run_id = ?",
        (crashed_run,),
    ) == [(0,)]
    recovered = stored_report(tmp_data_root, crashed_run)
    assert recovered["status"] == "FAILED"
    assert recovered["cause"] == RECOVERY_CAUSE
    parse_utc(recovered["finished_at"])
    assert (tmp_data_root / "raw" / "resources" / sha / "payload").read_bytes() == (
        content
    )
    assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_r_divergent_orphan_fails_without_overwrite(
    tmp_data_root: Path, synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"orfao que sera corrompido"
    path, sha = synthetic_file(content)
    crash_between_publication_and_commit(tmp_data_root, path, monkeypatch)
    payload = tmp_data_root / "raw" / "resources" / sha / "payload"
    corrupted = b"Z" + content[1:]
    payload.write_bytes(corrupted)

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == failed_unit()
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("recovery", "INFO"),
        ("orphan_reconciliation", "ERROR"),
    ]
    assert report["issues"][1]["resource_id"] is None
    assert payload.read_bytes() == corrupted
    assert db_rows(tmp_data_root, "SELECT count(*) FROM source_resource") == [(0,)]
    assert db_rows(tmp_data_root, "SELECT count(*) FROM resource_acquisition") == [(0,)]
    assert_consistent_run(tmp_data_root, report)


def test_acceptance_case_r_interrupted_copy_and_abandoned_run_recovered(
    tmp_data_root: Path,
    fresh_db: sqlite3.Connection,
    resources_fd: int,
    synthetic_file,
) -> None:
    abandoned = create_run(fresh_db, {})
    fresh_db.commit()
    tmp_fd, tmp_name = create_temp_file(resources_fd, abandoned.id)
    try:
        os.write(tmp_fd, b"copia interrompida")
    finally:
        os.close(tmp_fd)
    path, sha = synthetic_file(b"nova entrada")

    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "SUCCESS"
    # Temporário nunca vira recurso: removido e não registrado.
    assert resource_entries(tmp_data_root) == [sha]
    assert [row[1] for row in resource_rows(tmp_data_root)] == [sha]
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("recovery", "INFO"),
        ("temp_cleanup", "INFO"),
    ]
    assert tmp_name in report["issues"][1]["message"]
    recovered = get_ingestion_run_by_id(fresh_db, abandoned.id)
    assert recovered.status == "FAILED"
    assert parse_utc(recovered.finished_at) >= parse_utc(abandoned.started_at)
    assert json.loads(recovered.results) == {"cause": RECOVERY_CAUSE}
    assert_consistent_run(tmp_data_root, report)


@pytest.mark.parametrize("existing", [False, True], ids=["create", "reuse"])
def test_acceptance_case_r_sqlite_failure_leaves_no_partial_records(
    tmp_data_root: Path,
    synthetic_file,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    content = b"transacao recurso + aquisicao"
    path, sha = synthetic_file(content)
    resources_before: list[tuple] = []
    acquisitions_before: list[tuple] = []
    if existing:
        ingest_file(tmp_data_root, path)
        resources_before = resource_rows(tmp_data_root)
        acquisitions_before = db_rows(
            tmp_data_root, "SELECT * FROM resource_acquisition"
        )

    def broken_acquisition(conn, acquisition):
        raise sqlite3.OperationalError("falha simulada na aquisição")

    monkeypatch.setattr(ingest, "insert_resource_acquisition", broken_acquisition)
    report = ingest_file(tmp_data_root, path)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == failed_unit()
    assert [(i["stage"], i["severity"]) for i in report["issues"]] == [
        ("persistence", "FATAL")
    ]
    # Recurso inserido na mesma transação foi desfeito com a aquisição.
    assert resource_rows(tmp_data_root) == resources_before
    assert (
        db_rows(tmp_data_root, "SELECT * FROM resource_acquisition")
        == acquisitions_before
    )
    assert resource_entries(tmp_data_root) == [sha]
    assert_consistent_run(tmp_data_root, report)
    monkeypatch.undo()
    retry = ingest_file(tmp_data_root, path)
    assert retry["status"] == "SUCCESS"
    assert_consistent_run(tmp_data_root, retry)


def test_acceptance_counters_parameter_failure_is_not_a_preservation_attempt(
    tmp_data_root: Path, synthetic_file
) -> None:
    path, _ = synthetic_file(b"parametros invalidos")

    report = ingest_file(tmp_data_root, path, max_input_bytes=-1, fixture_kind="X")

    assert report["status"] == "FAILED"
    assert counters_of(report) == (0, 0, 0, 0)
    # A unidade solicitada continua identificável como falha (FR-013).
    assert report["units"] == failed_unit()
    assert {i["stage"] for i in report["issues"]} == {"parameters"}
    assert report["acquisitions"] == []
    assert resource_entries(tmp_data_root) == []
    assert_consistent_run(tmp_data_root, report)


def broken_publish(*args: object) -> str:
    raise OSError(errno.ENOSPC, "sem espaço simulado")


def broken_resource_insert(*args: object) -> None:
    raise sqlite3.OperationalError("falha simulada")


@pytest.mark.parametrize(
    ("kind", "stage"),
    [
        ("missing_input", "input"),
        ("rejected_input", "input"),
        ("limit_exceeded", "preserve"),
        ("divergent_payload", "dedup"),
        ("storage_failure", "publish"),
        ("persistence_failure", "persistence"),
    ],
)
def test_acceptance_counters_failed_preservation_attempt(
    tmp_data_root: Path,
    tmp_path: Path,
    synthetic_file,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    stage: str,
) -> None:
    content = b"tentativa de preservacao"
    path, sha = synthetic_file(content)
    options: dict[str, object] = {}
    if kind == "missing_input":
        path = make_missing(tmp_path)
    elif kind == "rejected_input":
        path = make_directory(tmp_path)
    elif kind == "limit_exceeded":
        options["max_input_bytes"] = len(content) - 1
    elif kind == "divergent_payload":
        ingest_file(tmp_data_root, path)
        payload = tmp_data_root / "raw" / "resources" / sha / "payload"
        payload.write_bytes(b"?" + content[1:])
    elif kind == "storage_failure":
        monkeypatch.setattr(ingest, "publish_payload", broken_publish)
    else:
        monkeypatch.setattr(ingest, "insert_source_resource", broken_resource_insert)

    report = ingest_file(tmp_data_root, path, **options)

    assert report["status"] == "FAILED"
    assert counters_of(report) == (1, 0, 0, 1)
    assert report["units"] == failed_unit()
    assert report["issues"][-1]["stage"] == stage
    assert report["acquisitions"] == []
    assert_consistent_run(tmp_data_root, report)
