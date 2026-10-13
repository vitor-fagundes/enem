"""Schema e conexão SQLite dos metadados operacionais de ingestão (SPEC-004)."""

import sqlite3
from dataclasses import astuple, dataclass, fields
from os import PathLike

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    id TEXT PRIMARY KEY NOT NULL,
    pipeline_name TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED')),
    parameters TEXT NOT NULL,
    code_revision TEXT,
    results TEXT
);

CREATE TABLE IF NOT EXISTS source_resource (
    id TEXT PRIMARY KEY NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    media_type TEXT,
    storage_locator TEXT NOT NULL,
    registered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resource_acquisition (
    id TEXT PRIMARY KEY NOT NULL,
    resource_id TEXT NOT NULL REFERENCES source_resource (id),
    ingestion_run_id TEXT NOT NULL REFERENCES ingestion_run (id),
    acquisition_method TEXT NOT NULL
        CHECK (acquisition_method IN ('LOCAL_FILE', 'CONTAINER_MEMBER', 'FIXTURE')),
    observed_at TEXT NOT NULL,
    source_definition_id TEXT,
    source_url TEXT,
    provider TEXT,
    received_filename TEXT,
    parent_resource_id TEXT REFERENCES source_resource (id),
    container_locator TEXT,
    source_retrieved_at TEXT,
    fixture_kind TEXT
        CHECK (fixture_kind IN ('SYNTHETIC', 'DERIVED_FROM_REAL')),
    CHECK (
        acquisition_method <> 'CONTAINER_MEMBER'
        OR (parent_resource_id IS NOT NULL AND container_locator IS NOT NULL)
    ),
    CHECK (acquisition_method <> 'FIXTURE' OR fixture_kind IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS ingestion_issue (
    id TEXT PRIMARY KEY NOT NULL,
    run_id TEXT NOT NULL REFERENCES ingestion_run (id),
    stage TEXT NOT NULL,
    severity TEXT NOT NULL
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'FATAL')),
    message TEXT NOT NULL,
    resource_id TEXT REFERENCES source_resource (id),
    input_reference TEXT,
    locator TEXT,
    exception_type TEXT
);
"""


def get_connection(db_path: str | PathLike[str]) -> sqlite3.Connection:
    """Abre conexão com chaves estrangeiras ativas; falha se não forem suportadas."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("PRAGMA foreign_keys").fetchone() != (1,):
        conn.close()
        raise RuntimeError("SQLite sem suporte a foreign_keys; integridade exigida.")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Cria as tabelas ausentes; chamadas repetidas não alteram dados existentes."""
    # executescript() faria COMMIT implícito da transação aberta pelo chamador.
    if conn.in_transaction:
        raise RuntimeError("ensure_schema() exige conexão sem transação ativa.")
    conn.executescript(SCHEMA)


# Campos JSON (`parameters`, `results`, `locator`) são mantidos como texto serializado.


@dataclass(frozen=True)
class IngestionRun:
    id: str
    pipeline_name: str
    pipeline_version: str
    started_at: str
    finished_at: str | None
    status: str
    parameters: str
    code_revision: str | None
    results: str | None


@dataclass(frozen=True)
class SourceResource:
    id: str
    sha256: str
    byte_size: int
    media_type: str | None
    storage_locator: str
    registered_at: str


@dataclass(frozen=True)
class ResourceAcquisition:
    id: str
    resource_id: str
    ingestion_run_id: str
    acquisition_method: str
    observed_at: str
    source_definition_id: str | None
    source_url: str | None
    provider: str | None
    received_filename: str | None
    parent_resource_id: str | None
    container_locator: str | None
    source_retrieved_at: str | None
    fixture_kind: str | None


@dataclass(frozen=True)
class IngestionIssue:
    id: str
    run_id: str
    stage: str
    severity: str
    message: str
    resource_id: str | None
    input_reference: str | None
    locator: str | None
    exception_type: str | None


def _insert(conn: sqlite3.Connection, table: str, entity: object) -> None:
    # Não faz commit: o controle transacional é do chamador.
    columns = [field.name for field in fields(entity)]
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        astuple(entity),
    )


def _get_by_id[T](
    conn: sqlite3.Connection, table: str, entity_type: type[T], entity_id: str
) -> T | None:
    columns = ", ".join(field.name for field in fields(entity_type))
    row = conn.execute(
        f"SELECT {columns} FROM {table} WHERE id = ?", (entity_id,)
    ).fetchone()
    return None if row is None else entity_type(*row)


def insert_ingestion_run(conn: sqlite3.Connection, run: IngestionRun) -> None:
    _insert(conn, "ingestion_run", run)


def get_ingestion_run_by_id(
    conn: sqlite3.Connection, run_id: str
) -> IngestionRun | None:
    return _get_by_id(conn, "ingestion_run", IngestionRun, run_id)


def insert_source_resource(conn: sqlite3.Connection, resource: SourceResource) -> None:
    _insert(conn, "source_resource", resource)


def get_source_resource_by_id(
    conn: sqlite3.Connection, resource_id: str
) -> SourceResource | None:
    return _get_by_id(conn, "source_resource", SourceResource, resource_id)


def insert_resource_acquisition(
    conn: sqlite3.Connection, acquisition: ResourceAcquisition
) -> None:
    _insert(conn, "resource_acquisition", acquisition)


def get_resource_acquisition_by_id(
    conn: sqlite3.Connection, acquisition_id: str
) -> ResourceAcquisition | None:
    return _get_by_id(conn, "resource_acquisition", ResourceAcquisition, acquisition_id)


def insert_ingestion_issue(conn: sqlite3.Connection, issue: IngestionIssue) -> None:
    _insert(conn, "ingestion_issue", issue)


def get_ingestion_issue_by_id(
    conn: sqlite3.Connection, issue_id: str
) -> IngestionIssue | None:
    return _get_by_id(conn, "ingestion_issue", IngestionIssue, issue_id)
