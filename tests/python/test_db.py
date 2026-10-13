"""Invariantes do schema SQLite e entidades da ingestão local (SPEC-004)."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from enem_rei_ingestion.db import (
    IngestionIssue,
    IngestionRun,
    ResourceAcquisition,
    SourceResource,
    ensure_schema,
    get_connection,
    get_ingestion_issue_by_id,
    get_ingestion_run_by_id,
    get_resource_acquisition_by_id,
    get_source_resource_by_id,
    insert_ingestion_issue,
    insert_ingestion_run,
    insert_resource_acquisition,
    insert_source_resource,
)

TS = "2026-10-12T00:00:00Z"


@pytest.fixture
def conn(fresh_db: sqlite3.Connection) -> sqlite3.Connection:
    return fresh_db


def insert_run(conn: sqlite3.Connection, run_id: str = "run-1", **overrides) -> None:
    row = {
        "id": run_id,
        "pipeline_name": "local_file",
        "pipeline_version": "0.1.0",
        "started_at": TS,
        "status": "RUNNING",
        "parameters": "{}",
        **overrides,
    }
    conn.execute(
        "INSERT INTO ingestion_run"
        " (id, pipeline_name, pipeline_version, started_at, status, parameters)"
        " VALUES (:id, :pipeline_name, :pipeline_version, :started_at, :status,"
        " :parameters)",
        row,
    )


def insert_resource(
    conn: sqlite3.Connection, resource_id: str = "res-1", sha256: str = "a" * 64
) -> None:
    conn.execute(
        "INSERT INTO source_resource"
        " (id, sha256, byte_size, storage_locator, registered_at)"
        " VALUES (?, ?, 0, ?, ?)",
        (resource_id, sha256, f"raw/resources/{sha256}/payload", TS),
    )


def insert_acquisition(
    conn: sqlite3.Connection,
    resource_id: str = "res-1",
    run_id: str = "run-1",
    method: str = "LOCAL_FILE",
    **optional: str,
) -> None:
    row = {
        "id": "acq-1",
        "resource_id": resource_id,
        "ingestion_run_id": run_id,
        "acquisition_method": method,
        "observed_at": TS,
        **optional,
    }
    columns = ", ".join(row)
    placeholders = ", ".join(f":{column}" for column in row)
    conn.execute(
        f"INSERT INTO resource_acquisition ({columns}) VALUES ({placeholders})", row
    )


VALID_METHOD_FIELDS = {
    "LOCAL_FILE": {},
    "CONTAINER_MEMBER": {
        "parent_resource_id": "zip-1",
        "container_locator": "dados/item.csv",
    },
    "FIXTURE": {"fixture_kind": "SYNTHETIC"},
}


@pytest.fixture
def acquisition_ready(conn: sqlite3.Connection) -> sqlite3.Connection:
    insert_run(conn)
    insert_resource(conn)
    insert_resource(conn, resource_id="zip-1", sha256="b" * 64)
    return conn


def insert_issue(
    conn: sqlite3.Connection, run_id: str = "run-1", severity: str = "ERROR"
) -> None:
    conn.execute(
        "INSERT INTO ingestion_issue (id, run_id, stage, severity, message)"
        " VALUES ('iss-1', ?, 'validation', ?, 'falha')",
        (run_id, severity),
    )


def test_foreign_keys_enabled_on_every_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "ingestion.db"
    for _ in range(2):
        connection = get_connection(db_path)
        try:
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        finally:
            connection.close()


def test_acquisition_rejects_missing_resource(conn: sqlite3.Connection) -> None:
    insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_acquisition(conn, resource_id="missing")


def test_acquisition_rejects_missing_run(conn: sqlite3.Connection) -> None:
    insert_resource(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_acquisition(conn, run_id="missing")


def test_issue_rejects_missing_run(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_issue(conn, run_id="missing")


@pytest.mark.parametrize("status", ["RUNNING", "SUCCESS", "PARTIAL", "FAILED"])
def test_run_status_accepts_allowed_values(
    conn: sqlite3.Connection, status: str
) -> None:
    insert_run(conn, status=status)


@pytest.mark.parametrize("status", ["DONE", "running", ""])
def test_run_status_rejects_other_values(conn: sqlite3.Connection, status: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_run(conn, status=status)


@pytest.mark.parametrize("method", ["LOCAL_FILE", "CONTAINER_MEMBER", "FIXTURE"])
def test_acquisition_method_accepts_allowed_values(
    acquisition_ready: sqlite3.Connection, method: str
) -> None:
    insert_acquisition(acquisition_ready, method=method, **VALID_METHOD_FIELDS[method])


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"container_locator": "dados/item.csv"},
        {"parent_resource_id": "zip-1"},
    ],
)
def test_container_member_requires_parent_and_locator(
    acquisition_ready: sqlite3.Connection, fields: dict[str, str]
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_acquisition(acquisition_ready, method="CONTAINER_MEMBER", **fields)


def test_container_member_accepts_propagated_fixture_kind(
    acquisition_ready: sqlite3.Connection,
) -> None:
    insert_acquisition(
        acquisition_ready,
        method="CONTAINER_MEMBER",
        fixture_kind="SYNTHETIC",
        **VALID_METHOD_FIELDS["CONTAINER_MEMBER"],
    )


def test_fixture_requires_fixture_kind(acquisition_ready: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_acquisition(acquisition_ready, method="FIXTURE")


@pytest.mark.parametrize("method", ["HTTP_DOWNLOAD", "local_file", ""])
def test_acquisition_method_rejects_other_values(
    conn: sqlite3.Connection, method: str
) -> None:
    insert_run(conn)
    insert_resource(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_acquisition(conn, method=method)


@pytest.mark.parametrize("severity", ["INFO", "WARNING", "ERROR", "FATAL"])
def test_issue_severity_accepts_allowed_values(
    conn: sqlite3.Connection, severity: str
) -> None:
    insert_run(conn)
    insert_issue(conn, severity=severity)


@pytest.mark.parametrize("severity", ["CRITICAL", "error", ""])
def test_issue_severity_rejects_other_values(
    conn: sqlite3.Connection, severity: str
) -> None:
    insert_run(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_issue(conn, severity=severity)


def test_resource_sha256_is_unique(conn: sqlite3.Connection) -> None:
    insert_resource(conn, resource_id="res-1")
    with pytest.raises(sqlite3.IntegrityError):
        insert_resource(conn, resource_id="res-2")


def test_ensure_schema_is_idempotent(conn: sqlite3.Connection) -> None:
    insert_run(conn)
    conn.commit()
    ensure_schema(conn)
    assert conn.execute("SELECT count(*) FROM ingestion_run").fetchone() == (1,)


# (nome, tipo, restrição) na ordem de data-model.md; "PK" marca a chave primária.
EXPECTED_COLUMNS = {
    "ingestion_run": [
        ("id", "TEXT", "PK NOT NULL"),
        ("pipeline_name", "TEXT", "NOT NULL"),
        ("pipeline_version", "TEXT", "NOT NULL"),
        ("started_at", "TEXT", "NOT NULL"),
        ("finished_at", "TEXT", "NULL"),
        ("status", "TEXT", "NOT NULL"),
        ("parameters", "TEXT", "NOT NULL"),
        ("code_revision", "TEXT", "NULL"),
        ("results", "TEXT", "NULL"),
    ],
    "source_resource": [
        ("id", "TEXT", "PK NOT NULL"),
        ("sha256", "TEXT", "NOT NULL"),
        ("byte_size", "INTEGER", "NOT NULL"),
        ("media_type", "TEXT", "NULL"),
        ("storage_locator", "TEXT", "NOT NULL"),
        ("registered_at", "TEXT", "NOT NULL"),
    ],
    "resource_acquisition": [
        ("id", "TEXT", "PK NOT NULL"),
        ("resource_id", "TEXT", "NOT NULL"),
        ("ingestion_run_id", "TEXT", "NOT NULL"),
        ("acquisition_method", "TEXT", "NOT NULL"),
        ("observed_at", "TEXT", "NOT NULL"),
        ("source_definition_id", "TEXT", "NULL"),
        ("source_url", "TEXT", "NULL"),
        ("provider", "TEXT", "NULL"),
        ("received_filename", "TEXT", "NULL"),
        ("parent_resource_id", "TEXT", "NULL"),
        ("container_locator", "TEXT", "NULL"),
        ("source_retrieved_at", "TEXT", "NULL"),
        ("fixture_kind", "TEXT", "NULL"),
    ],
    "ingestion_issue": [
        ("id", "TEXT", "PK NOT NULL"),
        ("run_id", "TEXT", "NOT NULL"),
        ("stage", "TEXT", "NOT NULL"),
        ("severity", "TEXT", "NOT NULL"),
        ("message", "TEXT", "NOT NULL"),
        ("resource_id", "TEXT", "NULL"),
        ("input_reference", "TEXT", "NULL"),
        ("locator", "TEXT", "NULL"),
        ("exception_type", "TEXT", "NULL"),
    ],
}

EXPECTED_FOREIGN_KEYS = {
    "ingestion_run": set(),
    "source_resource": set(),
    "resource_acquisition": {
        ("resource_id", "source_resource", "id"),
        ("ingestion_run_id", "ingestion_run", "id"),
        ("parent_resource_id", "source_resource", "id"),
    },
    "ingestion_issue": {
        ("run_id", "ingestion_run", "id"),
        ("resource_id", "source_resource", "id"),
    },
}


def test_fresh_schema_has_expected_tables_and_columns(
    conn: sqlite3.Connection,
) -> None:
    for table, columns in EXPECTED_COLUMNS.items():
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        actual = [
            (
                name,
                type_,
                ("PK " if pk else "") + ("NOT NULL" if notnull else "NULL"),
            )
            for _, name, type_, notnull, _, pk in rows
        ]
        assert actual == columns


def test_schema_declares_expected_foreign_keys(conn: sqlite3.Connection) -> None:
    for table, expected in EXPECTED_FOREIGN_KEYS.items():
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        assert {(row[3], row[2], row[4]) for row in rows} == expected


def test_schema_declares_unique_sha256_only(conn: sqlite3.Connection) -> None:
    unique_columns = {
        (table, column)
        for table in EXPECTED_COLUMNS
        for _, index, _, origin, _ in conn.execute(f"PRAGMA index_list({table})")
        if origin == "u"
        for _, _, column in conn.execute(f"PRAGMA index_info({index})")
    }
    assert unique_columns == {("source_resource", "sha256")}


def test_resource_byte_size_rejects_negative(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert_source_resource(conn, make_resource(byte_size=-1))


def make_run(**overrides) -> IngestionRun:
    values = {
        "id": "run-1",
        "pipeline_name": "local_file",
        "pipeline_version": "0.1.0",
        "started_at": TS,
        "finished_at": None,
        "status": "RUNNING",
        "parameters": "{}",
        "code_revision": None,
        "results": None,
        **overrides,
    }
    return IngestionRun(**values)


def make_resource(**overrides) -> SourceResource:
    values = {
        "id": "res-1",
        "sha256": "a" * 64,
        "byte_size": 0,
        "media_type": None,
        "storage_locator": f"raw/resources/{'a' * 64}/payload",
        "registered_at": TS,
        **overrides,
    }
    return SourceResource(**values)


def make_acquisition(**overrides) -> ResourceAcquisition:
    values = {
        "id": "acq-1",
        "resource_id": "res-1",
        "ingestion_run_id": "run-1",
        "acquisition_method": "LOCAL_FILE",
        "observed_at": TS,
        "source_definition_id": None,
        "source_url": None,
        "provider": None,
        "received_filename": None,
        "parent_resource_id": None,
        "container_locator": None,
        "source_retrieved_at": None,
        "fixture_kind": None,
        **overrides,
    }
    return ResourceAcquisition(**values)


def make_issue(**overrides) -> IngestionIssue:
    values = {
        "id": "iss-1",
        "run_id": "run-1",
        "stage": "validation",
        "severity": "ERROR",
        "message": "falha",
        "resource_id": None,
        "input_reference": None,
        "locator": None,
        "exception_type": None,
        **overrides,
    }
    return IngestionIssue(**values)


def test_ingestion_run_round_trip_with_nulls(conn: sqlite3.Connection) -> None:
    run = make_run()
    insert_ingestion_run(conn, run)
    assert get_ingestion_run_by_id(conn, run.id) == run


def test_ingestion_run_round_trip_with_all_fields(conn: sqlite3.Connection) -> None:
    run = make_run(
        finished_at="2026-10-12T00:01:00Z",
        status="SUCCESS",
        parameters='{"max_input_bytes": 1024}',
        code_revision="a681bfc",
        results='{"resources_created": 1}',
    )
    insert_ingestion_run(conn, run)
    assert get_ingestion_run_by_id(conn, run.id) == run


def test_source_resource_round_trip_with_nulls(conn: sqlite3.Connection) -> None:
    resource = make_resource()
    insert_source_resource(conn, resource)
    assert get_source_resource_by_id(conn, resource.id) == resource


def test_source_resource_round_trip_with_all_fields(conn: sqlite3.Connection) -> None:
    resource = make_resource(byte_size=12345, media_type="application/zip")
    insert_source_resource(conn, resource)
    assert get_source_resource_by_id(conn, resource.id) == resource


def test_resource_acquisition_round_trip_with_nulls(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    insert_source_resource(conn, make_resource())
    acquisition = make_acquisition()
    insert_resource_acquisition(conn, acquisition)
    assert get_resource_acquisition_by_id(conn, acquisition.id) == acquisition


def test_resource_acquisition_round_trip_with_all_fields(
    conn: sqlite3.Connection,
) -> None:
    insert_ingestion_run(conn, make_run())
    insert_source_resource(conn, make_resource())
    insert_source_resource(conn, make_resource(id="zip-1", sha256="b" * 64))
    acquisition = make_acquisition(
        acquisition_method="CONTAINER_MEMBER",
        source_definition_id="inep-microdados",
        source_url="https://example.invalid/arquivo.zip",
        provider="INEP",
        received_filename="arquivo.zip",
        parent_resource_id="zip-1",
        container_locator="dados/item.csv",
        source_retrieved_at="2026-10-11T00:00:00Z",
        fixture_kind="DERIVED_FROM_REAL",
    )
    insert_resource_acquisition(conn, acquisition)
    assert get_resource_acquisition_by_id(conn, acquisition.id) == acquisition


def test_ingestion_issue_round_trip_with_nulls(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    issue = make_issue()
    insert_ingestion_issue(conn, issue)
    assert get_ingestion_issue_by_id(conn, issue.id) == issue


def test_ingestion_issue_round_trip_with_all_fields(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    insert_source_resource(conn, make_resource())
    issue = make_issue(
        resource_id="res-1",
        input_reference="entrada/arquivo.zip",
        locator='{"resource_id": "res-1", "locator_type": "DOCUMENT"}',
        exception_type="ValueError",
    )
    insert_ingestion_issue(conn, issue)
    assert get_ingestion_issue_by_id(conn, issue.id) == issue


def test_get_by_id_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    assert get_ingestion_run_by_id(conn, "missing") is None
    assert get_source_resource_by_id(conn, "missing") is None
    assert get_resource_acquisition_by_id(conn, "missing") is None
    assert get_ingestion_issue_by_id(conn, "missing") is None


def test_insert_helper_rejects_dangling_foreign_key(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    with pytest.raises(sqlite3.IntegrityError):
        insert_resource_acquisition(conn, make_acquisition(resource_id="missing"))


def test_insert_helpers_leave_transaction_to_caller(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    insert_source_resource(conn, make_resource())
    insert_resource_acquisition(conn, make_acquisition())
    insert_ingestion_issue(conn, make_issue())
    assert conn.in_transaction
    conn.rollback()
    assert get_ingestion_run_by_id(conn, "run-1") is None
    assert get_source_resource_by_id(conn, "res-1") is None
    assert get_resource_acquisition_by_id(conn, "acq-1") is None
    assert get_ingestion_issue_by_id(conn, "iss-1") is None


def test_ensure_schema_rejects_active_transaction(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    assert conn.in_transaction
    with pytest.raises(RuntimeError):
        ensure_schema(conn)
    assert conn.in_transaction
    conn.rollback()
    assert get_ingestion_run_by_id(conn, "run-1") is None


def test_issue_rejects_missing_resource(conn: sqlite3.Connection) -> None:
    insert_ingestion_run(conn, make_run())
    with pytest.raises(sqlite3.IntegrityError):
        insert_ingestion_issue(conn, make_issue(resource_id="missing"))


def test_simultaneous_connections_both_enforce_foreign_keys(
    fresh_db: sqlite3.Connection, tmp_data_root: Path
) -> None:
    second = get_connection(tmp_data_root / "ingestion.db")
    try:
        for connection in (fresh_db, second):
            with pytest.raises(sqlite3.IntegrityError):
                insert_ingestion_issue(connection, make_issue(run_id="missing"))
            # A falha mantém a transação implícita aberta e o lock de escrita.
            connection.rollback()
    finally:
        second.close()


@pytest.mark.parametrize(
    "insert_null_id",
    [
        lambda conn: insert_ingestion_run(conn, make_run(id=None)),
        lambda conn: insert_source_resource(
            conn, make_resource(id=None, sha256="c" * 64)
        ),
        lambda conn: insert_resource_acquisition(conn, make_acquisition(id=None)),
        lambda conn: insert_ingestion_issue(conn, make_issue(id=None)),
    ],
    ids=list(EXPECTED_COLUMNS),
)
def test_primary_key_rejects_null_id(
    conn: sqlite3.Connection, insert_null_id: Callable[[sqlite3.Connection], None]
) -> None:
    insert_ingestion_run(conn, make_run())
    insert_source_resource(conn, make_resource())
    with pytest.raises(sqlite3.IntegrityError):
        insert_null_id(conn)
