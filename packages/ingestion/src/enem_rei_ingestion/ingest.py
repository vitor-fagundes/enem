"""Run, aquisições, issues e relatório da ingestão local (SPEC-004)."""

import errno
import json
import os
import sqlite3
import stat
import sys
import uuid
from collections.abc import Mapping
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime

from enem_rei_ingestion import __version__
from enem_rei_ingestion.db import (
    IngestionIssue,
    IngestionRun,
    ResourceAcquisition,
    SourceResource,
    get_ingestion_run_by_id,
    get_source_resource_by_id,
    insert_ingestion_issue,
    insert_ingestion_run,
    insert_resource_acquisition,
    insert_source_resource,
)
from enem_rei_ingestion.hasher import SizeLimitExceeded, stream_verify_hash
from enem_rei_ingestion.store import (
    PAYLOAD_NAME,
    RESOURCES_PATH,
    SHA256_HEX,
    UnsafeStoragePath,
)

PIPELINE_NAME = "enem_rei_ingestion"
RESOURCE_COUNTERS = (
    "resources_seen",
    "resources_created",
    "resources_reused",
    "resources_failed",
)
# Sem parsing neste incremento: contadores de registros não se aplicam (FR-013).
RECORD_COUNTERS = ("records_read", "records_accepted", "records_rejected")
RECOVERY_CAUSE = "recovered_after_interruption"
ORPHAN_STAGE = "orphan_reconciliation"


class ReportUnavailable(Exception):
    """O estado persistido em SQLite não permite um relatório fiel do run."""


class OrphanPayloadDivergent(Exception):
    """Payload órfão não confere com hash/tamanho esperados; não pode ser adotado."""


# Limite padrão de bytes lidos de cada arquivo de entrada (arquivo local ou ZIP),
# aplicado durante a cópia em streaming (FR-018, INV-004-017). 2 GiB comporta os
# arquivos oficiais esperados e mantém o limite finito; o valor efetivo é
# registrado em `parameters` do run. Override explícito aceita inteiro >= 0;
# ausente ou `None` usa este padrão, nunca desativa o limite.
DEFAULT_MAX_INPUT_BYTES = 2 * 1024**3

FINAL_STATUSES = ("SUCCESS", "FAILED")


def create_run(
    conn: sqlite3.Connection, parameters: Mapping[str, object]
) -> IngestionRun:
    """Registra um run `RUNNING` sem commit; o chamador controla a transação.

    A identidade do run é alocada antes de qualquer validação ou persistência.
    `parameters` recebe o `max_input_bytes` efetivo. Se o run não puder ser
    persistido, emite diagnóstico `FATAL` em stderr com o id alocado e propaga a
    falha: nenhum payload pode ser publicado sem run registrado (FR-011).
    """
    run_id = str(uuid.uuid4())
    effective = {
        **parameters,
        "max_input_bytes": _effective_max_input_bytes(
            parameters.get("max_input_bytes")
        ),
    }
    run = IngestionRun(
        id=run_id,
        pipeline_name=PIPELINE_NAME,
        pipeline_version=__version__,
        started_at=_utc_now(),
        finished_at=None,
        status="RUNNING",
        parameters=json.dumps(effective, sort_keys=True),
        code_revision=None,
        results=None,
    )
    try:
        insert_ingestion_run(conn, run)
    except sqlite3.Error as exc:
        print(
            f"FATAL: não foi possível registrar o run {run_id} em SQLite: {exc}",
            file=sys.stderr,
        )
        raise
    return run


def finalize_run(
    conn: sqlite3.Connection,
    run: IngestionRun,
    status: str,
    results: Mapping[str, object],
) -> IngestionRun:
    """Finaliza um run `RUNNING` como `SUCCESS` ou `FAILED`, sem commit."""
    if status not in FINAL_STATUSES:
        raise ValueError(f"status final não suportado: {status!r}")
    if run.status != "RUNNING":
        raise ValueError(f"run {run.id} já finalizado como {run.status}")
    finished = replace(
        run,
        status=status,
        finished_at=_utc_now(),
        results=json.dumps(results, sort_keys=True),
    )
    cursor = conn.execute(
        "UPDATE ingestion_run SET status = ?, finished_at = ?, results = ?"
        " WHERE id = ? AND status = 'RUNNING'",
        (finished.status, finished.finished_at, finished.results, run.id),
    )
    if cursor.rowcount != 1:
        raise ValueError(f"run {run.id} não está RUNNING no banco")
    return finished


def record_acquisition(
    conn: sqlite3.Connection,
    resource: SourceResource,
    run: IngestionRun,
    method: str,
    *,
    input_path: str | os.PathLike[str] | None = None,
    source_definition_id: str | None = None,
    source_url: str | None = None,
    provider: str | None = None,
    source_retrieved_at: str | None = None,
    parent_resource_id: str | None = None,
    container_locator: str | None = None,
    fixture_kind: str | None = None,
) -> ResourceAcquisition:
    """Registra uma aquisição do recurso neste run, sem commit.

    `observed_at` é o instante desta observação; metadados de origem ausentes
    ficam `None` e nunca são derivados de outros campos (FR-004). O
    `received_filename` é só o basename de `input_path`, quando informado. A
    validade de método e campos condicionais é garantida pelo schema SQLite.
    """
    if method in ("LOCAL_FILE", "FIXTURE") and (
        parent_resource_id is not None or container_locator is not None
    ):
        raise ValueError(f"{method} não tem recurso pai nem membro de contêiner")
    if method == "LOCAL_FILE" and fixture_kind is not None:
        raise ValueError("LOCAL_FILE não tem fixture_kind; use FIXTURE")
    acquisition = ResourceAcquisition(
        id=str(uuid.uuid4()),
        resource_id=resource.id,
        ingestion_run_id=run.id,
        acquisition_method=method,
        observed_at=_utc_now(),
        source_definition_id=source_definition_id,
        source_url=source_url,
        provider=provider,
        received_filename=(
            None if input_path is None else os.path.basename(os.fspath(input_path))
        ),
        parent_resource_id=parent_resource_id,
        container_locator=container_locator,
        source_retrieved_at=source_retrieved_at,
        fixture_kind=fixture_kind,
    )
    insert_resource_acquisition(conn, acquisition)
    return acquisition


def record_issue(
    conn: sqlite3.Connection,
    run_id: str,
    stage: str,
    severity: str,
    message: str,
    *,
    resource_id: str | None = None,
    input_reference: str | None = None,
    locator: Mapping[str, object] | None = None,
    exception_type: str | None = None,
) -> IngestionIssue:
    """Registra um issue do run, sem commit.

    `resource_id` pode ser `None` quando a falha ocorre antes de existir recurso
    (INV-004-011); `input_reference` identifica então a entrada. O `locator`
    (SourceLocator) é gravado como JSON e, com `resource_id`, deve apontar para
    o mesmo recurso (FR-013). Campos ausentes ficam `None`.
    """
    if locator is not None:
        if not isinstance(locator, Mapping) or not locator.get("resource_id"):
            raise ValueError("locator deve ser SourceLocator com resource_id")
        if resource_id is not None and locator["resource_id"] != resource_id:
            raise ValueError("locator e resource_id apontam recursos diferentes")
    issue = IngestionIssue(
        id=str(uuid.uuid4()),
        run_id=run_id,
        stage=stage,
        severity=severity,
        message=message,
        resource_id=resource_id,
        input_reference=input_reference,
        locator=None if locator is None else json.dumps(locator, sort_keys=True),
        exception_type=exception_type,
    )
    insert_ingestion_issue(conn, issue)
    return issue


def generate_report(conn: sqlite3.Connection, run: IngestionRun) -> dict:
    """Monta o relatório do run exclusivamente a partir do estado em SQLite.

    O run é relido do banco; contadores e unidades vêm de `results` persistido
    e `sha256`/`byte_size` de cada unidade vêm de `source_resource`. Run ainda
    `RUNNING` não tem resultados: contadores ficam `None` e unidades vazias, sem
    inferência a partir das aquisições. Estado ausente ou inconsistente gera
    `ReportUnavailable`, nunca um relatório preenchido por suposição.
    """
    persisted = get_ingestion_run_by_id(conn, run.id)
    if persisted is None:
        raise ReportUnavailable(f"run {run.id} não está registrado em SQLite")
    counters, units = _persisted_outcomes(conn, persisted)
    acquisitions = _rows_of_run(
        conn, ResourceAcquisition, "resource_acquisition", "ingestion_run_id", run.id
    )
    issues = _rows_of_run(conn, IngestionIssue, "ingestion_issue", "run_id", run.id)
    return {
        "run_id": persisted.id,
        "status": persisted.status,
        "started_at": persisted.started_at,
        "finished_at": persisted.finished_at,
        "pipeline_name": persisted.pipeline_name,
        "pipeline_version": persisted.pipeline_version,
        "parameters": json.loads(persisted.parameters),
        **counters,
        **dict.fromkeys(RECORD_COUNTERS),
        "units": units,
        "acquisitions": [asdict(acquisition) for acquisition in acquisitions],
        "issues": [
            {
                **asdict(issue),
                "locator": None if issue.locator is None else json.loads(issue.locator),
            }
            for issue in issues
        ],
        "cause": json.loads(persisted.results or "{}").get("cause"),
    }


def _persisted_outcomes(
    conn: sqlite3.Connection, run: IngestionRun
) -> tuple[dict[str, int | None], list[dict[str, object]]]:
    if run.results is None:
        return dict.fromkeys(RESOURCE_COUNTERS), []
    results = json.loads(run.results)
    # Run recuperado após interrupção pode não ter contadores nem unidades:
    # o que não foi registrado fica desconhecido (None/[]), nunca inventado.
    recovered = run.status == "FAILED" and results.get("cause") == RECOVERY_CAUSE
    counters = {name: results.get(name) for name in RESOURCE_COUNTERS}
    unknown = recovered and all(value is None for value in counters.values())
    if not unknown:
        _check_counters(run.id, counters)
    raw_units = results.get("units", [] if recovered else None)
    if not isinstance(raw_units, list):
        raise ReportUnavailable(f"run {run.id} sem resultados por unidade")
    units = []
    for unit in raw_units:
        resource_id = unit.get("resource_id")
        resource = None
        if resource_id is not None:
            resource = get_source_resource_by_id(conn, resource_id)
            if resource is None:
                raise ReportUnavailable(
                    f"run {run.id}: unidade cita recurso inexistente {resource_id}"
                )
        units.append(
            {
                "name": unit.get("name"),
                "status": unit.get("status"),
                "resource_id": resource_id,
                "sha256": None if resource is None else resource.sha256,
                "byte_size": None if resource is None else resource.byte_size,
            }
        )
    return counters, units


def _check_counters(run_id: str, counters: dict[str, object]) -> None:
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counters.values()
    ):
        raise ReportUnavailable(f"run {run_id} sem contadores válidos: {counters}")
    seen, *outcomes = counters.values()
    if seen != sum(outcomes):
        raise ReportUnavailable(
            f"run {run_id}: resources_seen != created + reused + failed"
        )


def _rows_of_run[T](
    conn: sqlite3.Connection,
    entity_type: type[T],
    table: str,
    run_column: str,
    run_id: str,
) -> list[T]:
    # Ordem de inserção (rowid) preserva a sequência registrada no run.
    columns = ", ".join(field.name for field in fields(entity_type))
    rows = conn.execute(
        f"SELECT {columns} FROM {table} WHERE {run_column} = ? ORDER BY rowid",
        (run_id,),
    ).fetchall()
    return [entity_type(*row) for row in rows]


def revalidate_existing(
    resources_fd: int, sha256_hex: str, expected_byte_size: int
) -> bool:
    """Confere se `<sha256_hex>/payload` ainda tem exatamente o conteúdo esperado.

    Recalcula SHA-256 e tamanho do payload armazenado (FR-016), lendo no máximo
    `expected_byte_size + 1` bytes. Retorna `False` se o payload estiver
    ausente, não for arquivo regular (inclui symlink, nunca seguido) ou
    divergir em hash ou tamanho, inclusive corrupção de mesmo tamanho.
    Diretório de hash que seja link ou não diretório gera `UnsafeStoragePath`;
    outros erros de filesystem são propagados. Somente leitura: decidir reuso,
    registrar issue ou aquisição cabe ao chamador.
    """
    if not isinstance(sha256_hex, str) or not SHA256_HEX.fullmatch(sha256_hex):
        raise ValueError(f"sha256 inválido: {sha256_hex!r}")
    if (
        isinstance(expected_byte_size, bool)
        or not isinstance(expected_byte_size, int)
        or expected_byte_size < 0
    ):
        raise ValueError(f"expected_byte_size inválido: {expected_byte_size!r}")

    try:
        sha256_fd = os.open(
            sha256_hex,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=resources_fd,
        )
    except FileNotFoundError:
        return False
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            component = "/".join((*RESOURCES_PATH, sha256_hex))
            raise UnsafeStoragePath(
                component, "link simbólico ou não é diretório"
            ) from exc
        raise
    try:
        try:
            # O_NONBLOCK impede bloqueio se o payload tiver virado FIFO.
            payload_fd = os.open(
                PAYLOAD_NAME,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=sha256_fd,
            )
        except FileNotFoundError:
            return False
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                return False
            raise
    finally:
        os.close(sha256_fd)

    try:
        is_regular = stat.S_ISREG(os.fstat(payload_fd).st_mode)
    except BaseException:
        os.close(payload_fd)
        raise
    if not is_regular:
        os.close(payload_fd)
        return False
    with os.fdopen(payload_fd, "rb") as payload:
        try:
            digest, byte_count = stream_verify_hash(
                payload, max_bytes=expected_byte_size
            )
        except SizeLimitExceeded:
            return False
    return digest == sha256_hex and byte_count == expected_byte_size


def recover_abandoned_runs(
    conn: sqlite3.Connection, *, current_run_id: str | None = None
) -> list[IngestionRun]:
    """Finaliza como `FAILED` os runs deixados em `RUNNING`, sem commit.

    Exige o lock exclusivo de escrita. `finished_at` é o instante desta
    recuperação (o da interrupção é desconhecido) e `results` recebe
    `cause = RECOVERY_CAUSE`, preservando o que já estiver registrado. Recursos,
    aquisições e issues confirmados não são alterados. `current_run_id` exclui
    o run da execução atual. Repetir a recuperação não altera nada.
    """
    running_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM ingestion_run WHERE status = 'RUNNING' ORDER BY rowid"
        )
    ]
    recovered = []
    for run_id in running_ids:
        if run_id == current_run_id:
            continue
        run = get_ingestion_run_by_id(conn, run_id)
        known = {} if run.results is None else json.loads(run.results)
        recovered.append(
            finalize_run(conn, run, "FAILED", {**known, "cause": RECOVERY_CAUSE})
        )
    return recovered


def reconcile_orphan(
    conn: sqlite3.Connection,
    resources_fd: int,
    run: IngestionRun,
    sha256_hex: str,
    byte_size: int,
    method: str = "LOCAL_FILE",
    *,
    media_type: str | None = None,
    **context: str | os.PathLike[str] | None,
) -> tuple[SourceResource, ResourceAcquisition]:
    """Registra payload órfão íntegro na reingestão explícita dos mesmos bytes.

    Órfão: `<sha256>/payload` publicado sem linha em `source_resource`
    (janela entre publicação e commit, FR-017). Só é adotado após
    `revalidate_existing` confirmar hash e tamanho; então registra recurso,
    uma aquisição do run atual (`context` como em `record_acquisition`) e issue
    `INFO` indicando a recuperação, sem commit e sem histórico fabricado.
    Divergência gera `OrphanPayloadDivergent` sem tocar no payload.
    """
    if conn.execute(
        "SELECT 1 FROM source_resource WHERE sha256 = ?", (sha256_hex,)
    ).fetchone():
        raise ValueError(f"sha256 {sha256_hex} já registrado; não é órfão")
    if not revalidate_existing(resources_fd, sha256_hex, byte_size):
        raise OrphanPayloadDivergent(
            f"payload órfão {sha256_hex} ausente ou divergente de {byte_size} bytes"
        )
    resource = SourceResource(
        id=str(uuid.uuid4()),
        sha256=sha256_hex,
        byte_size=byte_size,
        media_type=media_type,
        storage_locator="/".join((*RESOURCES_PATH, sha256_hex, PAYLOAD_NAME)),
        registered_at=_utc_now(),
    )
    insert_source_resource(conn, resource)
    acquisition = record_acquisition(conn, resource, run, method, **context)
    record_issue(
        conn,
        run.id,
        ORPHAN_STAGE,
        "INFO",
        "payload órfão íntegro registrado nesta execução; origem anterior desconhecida",
        resource_id=resource.id,
    )
    return resource, acquisition


def _effective_max_input_bytes(override: object) -> int:
    if override is None:
        return DEFAULT_MAX_INPUT_BYTES
    if isinstance(override, bool) or not isinstance(override, int) or override < 0:
        raise ValueError(f"max_input_bytes inválido: {override!r}")
    return override


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
