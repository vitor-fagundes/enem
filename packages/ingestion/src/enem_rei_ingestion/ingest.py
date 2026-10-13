"""Run, aquisições, issues e relatório da ingestão local (SPEC-004)."""

import errno
import json
import os
import sqlite3
import stat
import sys
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, fields, replace
from datetime import UTC, datetime
from typing import BinaryIO

from enem_rei_ingestion import __version__
from enem_rei_ingestion.db import (
    IngestionIssue,
    IngestionRun,
    ResourceAcquisition,
    SourceResource,
    ensure_schema,
    get_connection,
    get_ingestion_run_by_id,
    get_source_resource_by_id,
    insert_ingestion_issue,
    insert_ingestion_run,
    insert_resource_acquisition,
    insert_source_resource,
)
from enem_rei_ingestion.hasher import (
    SizeLimitExceeded,
    stream_copy_hash,
    stream_verify_hash,
)
from enem_rei_ingestion.store import (
    PAYLOAD_NAME,
    RESOURCES_PATH,
    SHA256_HEX,
    InputRejected,
    UnsafeStoragePath,
    WriterLockHeld,
    acquire_writer_lock,
    clean_orphan_temps,
    create_temp_file,
    open_storage_anchor,
    open_validated_input,
    publish_payload,
    release_writer_lock,
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
PRESERVE_UNIT = "preserve_input"
FIXTURE_KINDS = ("SYNTHETIC", "DERIVED_FROM_REAL")


class ReportUnavailable(Exception):
    """O estado persistido em SQLite não permite um relatório fiel do run."""


class OrphanPayloadDivergent(Exception):
    """Payload órfão não confere com hash/tamanho esperados; não pode ser adotado."""


class IngestionFatal(Exception):
    """Falha de infraestrutura que impede registrar ou finalizar o run (FATAL).

    O diagnóstico já foi emitido em stderr; `run_id` é `None` quando o run não
    chegou a ser registrado em SQLite. Nenhum relatório SQLite é fingido.
    """

    def __init__(self, message: str, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


class UnitFailed(Exception):
    """A unidade de preservação falhou; o issue `ERROR` já foi registrado."""

    def __init__(self, issue: IngestionIssue) -> None:
        super().__init__(issue.message)
        self.issue = issue


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

    `parameters` recebe o `max_input_bytes` efetivo; override inválido gera
    `ValueError` antes de persistir (o orquestrador registra esse caso como run
    `FAILED`, ver `ingest_local_file`). Se o run não puder ser persistido, emite
    diagnóstico `FATAL` em stderr com o id alocado e propaga a falha: nenhum
    payload pode ser publicado sem run registrado (FR-011).
    """
    effective = {
        **parameters,
        "max_input_bytes": _effective_max_input_bytes(
            parameters.get("max_input_bytes")
        ),
    }
    return _register_run(conn, effective)


def _register_run(
    conn: sqlite3.Connection, effective: Mapping[str, object]
) -> IngestionRun:
    # Persiste `effective` como recebido; validar limites cabe ao chamador.
    run_id = str(uuid.uuid4())
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


def ingest_local_file(
    db_path: str | os.PathLike[str],
    data_root: str | os.PathLike[str],
    input_path: str | os.PathLike[str],
    *,
    source_definition_id: str | None = None,
    source_url: str | None = None,
    provider: str | None = None,
    source_retrieved_at: str | None = None,
    fixture_kind: str | None = None,
    max_input_bytes: int | None = None,
) -> dict:
    """Ingere um arquivo local em um único run e devolve o relatório (FR-015).

    Ordem: lock exclusivo → SQLite + schema → run `RUNNING` com commit →
    recuperação de runs abandonados → limpeza de temporários órfãos → validação
    do input → `_preserve_file` → finalização com commit → relatório relido de
    SQLite. Toda invocação que obtém lock e banco registra exatamente um run,
    inclusive com input inexistente/rejeitado ou parâmetro inválido, finalizado
    `FAILED` com issue explicando a causa.

    Parâmetro inválido (`max_input_bytes` fora de inteiro >= 0, `fixture_kind`
    fora do domínio) não vira limite efetivo fictício: `parameters` grava
    `max_input_bytes = None` (nenhum limite aplicado, pois nada é lido) e o
    valor recebido em `rejected_parameters`; o input não é aberto.

    Contadores do run: uma unidade `preserve_input`. Contadores medem
    tentativas de preservação (FR-013): parâmetro inválido barra a unidade antes
    de qualquer tentativa, logo todos ficam 0 e a unidade fica `FAILED`. Nos
    demais casos `resources_seen = 1`; se a unidade não conclui (input,
    limite, divergência, armazenamento, persistência), `resources_failed = 1`
    e a unidade fica `FAILED` com `resource_id = None` (o issue referencia o
    recurso quando há).

    Falha ao obter o lock, abrir o banco, registrar ou finalizar o run gera
    `IngestionFatal` após diagnóstico em stderr; nada é publicado antes de o run
    estar persistido. `fixture_kind` informado usa o método `FIXTURE`.
    """
    context = {
        "source_definition_id": source_definition_id,
        "source_url": source_url,
        "provider": provider,
        "source_retrieved_at": source_retrieved_at,
        "fixture_kind": fixture_kind,
    }
    parameters, rejected = _local_file_parameters(input_path, context, max_input_bytes)

    try:
        lock_fd = acquire_writer_lock(data_root)
    except (WriterLockHeld, OSError) as exc:
        raise _fatal(f"lock de escrita indisponível em {data_root}: {exc}") from exc
    conn = None
    try:
        try:
            conn = get_connection(db_path)
            ensure_schema(conn)
        except (sqlite3.Error, RuntimeError) as exc:
            raise _fatal(f"SQLite indisponível em {db_path}: {exc}") from exc
        run = None
        try:
            if rejected:
                run = _register_run(conn, parameters)
            else:
                run = create_run(conn, parameters)
            conn.commit()
        except sqlite3.Error as exc:
            _rollback(conn)
            if run is None:  # create_run já emitiu o diagnóstico com o id alocado.
                raise IngestionFatal("run não registrado em SQLite") from exc
            raise _fatal(f"commit do run falhou: {exc}", run.id) from exc
        return _execute_local_file(conn, run, data_root, input_path, context, rejected)
    finally:
        if conn is not None:
            conn.close()
        release_writer_lock(lock_fd)


def _execute_local_file(
    conn: sqlite3.Connection,
    run: IngestionRun,
    data_root: str | os.PathLike[str],
    input_path: str | os.PathLike[str],
    context: Mapping[str, str | None],
    rejected: Mapping[str, str],
) -> dict:
    preserved = None
    persistence_error = None
    resources_fd = None
    try:
        try:
            resources_fd = _prepare_storage(conn, run, data_root)
            if resources_fd is not None:
                preserved = _preserve_input(
                    conn, resources_fd, run, input_path, context, rejected
                )
        except sqlite3.Error as exc:
            _rollback(conn)
            persistence_error = exc
    finally:
        if resources_fd is not None:
            os.close(resources_fd)

    unit = {"name": PRESERVE_UNIT, "status": "FAILED", "resource_id": None}
    counters = dict.fromkeys(RESOURCE_COUNTERS, 0)
    if preserved is None:
        # Parâmetro inválido barra a unidade antes de qualquer tentativa de
        # preservação: contadores ficam 0, mas a unidade segue FAILED (FR-013).
        if not rejected:
            counters["resources_seen"] = counters["resources_failed"] = 1
    else:
        counters["resources_seen"] = 1
        resource, _, outcome = preserved
        counters[f"resources_{outcome}"] = 1
        unit.update(status="SUCCESS", resource_id=resource.id)
    # Falha estrutural de persistência prevalece; unidade já confirmada fica.
    status = "SUCCESS" if preserved and persistence_error is None else "FAILED"
    try:
        if persistence_error is not None:
            record_issue(
                conn,
                run.id,
                "persistence",
                "FATAL",
                f"falha ao gravar em SQLite: {persistence_error}",
                exception_type=type(persistence_error).__name__,
            )
        finished = finalize_run(conn, run, status, {**counters, "units": [unit]})
        conn.commit()
    except sqlite3.Error as exc:
        _rollback(conn)
        # O run permanece RUNNING e será recuperado como FAILED (FR-017).
        raise _fatal(f"não foi possível finalizar o run: {exc}", run.id) from exc
    return generate_report(conn, finished)


def _prepare_storage(
    conn: sqlite3.Connection, run: IngestionRun, data_root: str | os.PathLike[str]
) -> int | None:
    # Sob o lock: recupera runs abandonados e limpa temporários de outros runs.
    # Retorna `resources_fd` (o chamador fecha) ou None se o armazenamento
    # estiver indisponível, caso em que registra issue FATAL.
    recovered = recover_abandoned_runs(conn, current_run_id=run.id)
    if recovered:
        record_issue(
            conn,
            run.id,
            "recovery",
            "INFO",
            "runs abandonados finalizados como FAILED: "
            + ", ".join(r.id for r in recovered),
        )
    resources_fd = None
    try:
        resources_fd = open_storage_anchor(data_root)
        removed = clean_orphan_temps(resources_fd, run.id)
    except (OSError, UnsafeStoragePath) as exc:
        if resources_fd is not None:
            os.close(resources_fd)
        record_issue(
            conn,
            run.id,
            "storage",
            "FATAL",
            f"armazenamento controlado indisponível: {exc}",
            exception_type=type(exc).__name__,
        )
        return None
    try:
        if removed:
            record_issue(
                conn,
                run.id,
                "temp_cleanup",
                "INFO",
                "temporários abandonados removidos: " + ", ".join(removed),
            )
        conn.commit()
    except BaseException:
        os.close(resources_fd)
        raise
    return resources_fd


def _preserve_input(
    conn: sqlite3.Connection,
    resources_fd: int,
    run: IngestionRun,
    input_path: str | os.PathLike[str],
    context: Mapping[str, str | None],
    rejected: Mapping[str, str],
) -> tuple[SourceResource, ResourceAcquisition, str] | None:
    # Unidade `preserve_input`; None quando falha com issue ERROR registrado.
    input_reference = os.fspath(input_path)
    if rejected:
        for name, value in rejected.items():
            record_issue(
                conn,
                run.id,
                "parameters",
                "ERROR",
                f"parâmetro inválido {name}={value}; input não processado",
                input_reference=input_reference,
            )
        return None
    try:
        input_file = open_validated_input(input_path)
    except (OSError, InputRejected) as exc:
        record_issue(
            conn,
            run.id,
            "input",
            "ERROR",
            f"input não pode ser lido: {exc}",
            input_reference=input_reference,
            exception_type=type(exc).__name__,
        )
        return None
    method = "LOCAL_FILE" if context["fixture_kind"] is None else "FIXTURE"
    max_bytes = json.loads(run.parameters)["max_input_bytes"]
    with input_file:
        try:
            return _preserve_file(
                conn,
                resources_fd,
                input_file,
                run,
                max_bytes,
                method,
                input_path=input_path,
                **context,
            )
        except UnitFailed:
            return None


def _preserve_file(
    conn: sqlite3.Connection,
    resources_fd: int,
    input_file: BinaryIO,
    run: IngestionRun,
    max_bytes: int,
    method: str = "LOCAL_FILE",
    **context: str | os.PathLike[str] | None,
) -> tuple[SourceResource, ResourceAcquisition, str]:
    """Preserva os bytes de `input_file` como recurso e registra a aquisição.

    Núcleo reutilizável dentro de um run e lock já obtidos (FR-015 passos 2–6):
    copia em streaming para temporário controlado calculando SHA-256 e tamanho
    na mesma leitura, sob `max_bytes` finito; faz flush/fsync/close e revalida o
    temporário (nunca relê a origem: se ela mudou durante a leitura, vale o
    hash dos bytes copiados). Depois: recurso já registrado só é reutilizado se
    `revalidate_existing` confirmar o payload; senão publica sem sobrescrita, e
    payload existente sem linha SQLite (órfão) segue `reconcile_orphan`.
    Recurso e aquisição são gravados na mesma transação, com commit (que também
    confirma o que o chamador tiver pendente) antes de retornar
    `(recurso, aquisição, "created" | "reused")`.

    Janela publicação→commit: se o processo cair após `os.link` e antes do
    commit, fica payload órfão sem linha em SQLite; ele é detectável e é
    reconciliado na reingestão dos mesmos bytes (FR-017, T-020).

    Falha da unidade registra issue `ERROR` sem commit e levanta `UnitFailed`;
    erro de SQLite faz rollback e é propagado. O temporário é removido em
    qualquer caminho e nunca vira recurso. `media_type` fica `None` (FR-021).
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise ValueError(f"max_bytes deve ser limite finito >= 0: {max_bytes!r}")
    input_path = context.get("input_path")
    input_reference = None if input_path is None else os.fspath(input_path)

    def fail(
        stage: str,
        message: str,
        exc: BaseException | None = None,
        resource_id: str | None = None,
    ) -> UnitFailed:
        issue = record_issue(
            conn,
            run.id,
            stage,
            "ERROR",
            message,
            resource_id=resource_id,
            input_reference=input_reference,
            exception_type=None if exc is None else type(exc).__name__,
        )
        return UnitFailed(issue)

    try:
        tmp_fd, tmp_name = create_temp_file(resources_fd, run.id)
    except OSError as exc:
        raise fail("preserve", f"falha ao criar temporário: {exc}", exc) from exc
    try:
        try:
            sha256_hex, byte_size = _copy_to_temp(tmp_fd, input_file, max_bytes)
        except SizeLimitExceeded as exc:
            raise fail(
                "preserve", f"input excede max_input_bytes={max_bytes}", exc
            ) from exc
        except OSError as exc:
            raise fail("preserve", f"falha na cópia do input: {exc}", exc) from exc
        try:
            verified = _verify_temp(resources_fd, tmp_name, byte_size)
        except OSError as exc:
            raise fail("preserve", f"falha ao validar temporário: {exc}", exc) from exc
        if verified != (sha256_hex, byte_size):
            raise fail("preserve", "temporário diverge do hash/tamanho copiados")
        try:
            return _register_preserved(
                conn,
                resources_fd,
                tmp_name,
                run,
                sha256_hex,
                byte_size,
                method,
                context,
                fail,
            )
        except sqlite3.Error:
            _rollback(conn)
            raise
    finally:
        try:
            os.unlink(tmp_name, dir_fd=resources_fd)
        except FileNotFoundError:
            pass  # Já publicado: `publish_payload` removeu o nome temporário.


def _register_preserved(
    conn: sqlite3.Connection,
    resources_fd: int,
    tmp_name: str,
    run: IngestionRun,
    sha256_hex: str,
    byte_size: int,
    method: str,
    context: Mapping[str, str | os.PathLike[str] | None],
    fail: Callable[..., UnitFailed],
) -> tuple[SourceResource, ResourceAcquisition, str]:
    row = conn.execute(
        "SELECT id FROM source_resource WHERE sha256 = ?", (sha256_hex,)
    ).fetchone()
    if row is not None:
        existing = get_source_resource_by_id(conn, row[0])
        try:
            intact = existing.byte_size == byte_size and revalidate_existing(
                resources_fd, sha256_hex, existing.byte_size
            )
        except (OSError, UnsafeStoragePath) as exc:
            raise fail(
                "dedup", f"falha ao revalidar payload: {exc}", exc, existing.id
            ) from exc
        if not intact:
            # FR-016: sem reuso, sem sobrescrita, sem corrigir metadados.
            raise fail(
                "dedup",
                f"payload registrado {sha256_hex} ausente ou divergente; reuso"
                " recusado e nada sobrescrito",
                resource_id=existing.id,
            )
        acquisition = record_acquisition(conn, existing, run, method, **context)
        conn.commit()
        return existing, acquisition, "reused"

    try:
        storage_locator = publish_payload(resources_fd, tmp_name, sha256_hex)
    except FileExistsError:
        try:
            resource, acquisition = reconcile_orphan(
                conn, resources_fd, run, sha256_hex, byte_size, method, **context
            )
        except (OrphanPayloadDivergent, OSError, UnsafeStoragePath) as exc:
            raise fail(
                ORPHAN_STAGE,
                f"payload órfão {sha256_hex} não adotado: {exc}",
                exc,
            ) from exc
        conn.commit()
        return resource, acquisition, "created"
    except (OSError, UnsafeStoragePath) as exc:
        raise fail("publish", f"falha ao publicar payload: {exc}", exc) from exc
    resource = SourceResource(
        id=str(uuid.uuid4()),
        sha256=sha256_hex,
        byte_size=byte_size,
        media_type=None,
        storage_locator=storage_locator,
        registered_at=_utc_now(),
    )
    insert_source_resource(conn, resource)
    acquisition = record_acquisition(conn, resource, run, method, **context)
    conn.commit()
    return resource, acquisition, "created"


def _copy_to_temp(tmp_fd: int, source: BinaryIO, max_bytes: int) -> tuple[str, int]:
    try:
        # Escrita bufferizada: `os.write` cru pode gravar parcialmente.
        tmp = os.fdopen(tmp_fd, "wb")
    except BaseException:
        os.close(tmp_fd)
        raise
    with tmp:
        digest = stream_copy_hash(source, tmp, max_bytes)
        tmp.flush()
        os.fsync(tmp.fileno())
    return digest


def _verify_temp(
    resources_fd: int, tmp_name: str, byte_size: int
) -> tuple[str, int] | None:
    # Relê apenas o temporário controlado (FR-015 passo 4), nunca a origem.
    fd = os.open(tmp_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=resources_fd)
    with os.fdopen(fd, "rb") as tmp:
        try:
            return stream_verify_hash(tmp, max_bytes=byte_size)
        except SizeLimitExceeded:
            return None


def _local_file_parameters(
    input_path: str | os.PathLike[str],
    context: Mapping[str, str | None],
    max_input_bytes: object,
) -> tuple[dict[str, object], dict[str, str]]:
    # Parâmetros do run e parâmetros rejeitados (nome → repr do valor recebido).
    parameters: dict[str, object] = {"input_path": os.fspath(input_path), **context}
    rejected: dict[str, str] = {}
    try:
        parameters["max_input_bytes"] = _effective_max_input_bytes(max_input_bytes)
    except ValueError:
        rejected["max_input_bytes"] = repr(max_input_bytes)
        parameters["max_input_bytes"] = None
    if context["fixture_kind"] not in (None, *FIXTURE_KINDS):
        rejected["fixture_kind"] = repr(context["fixture_kind"])
        parameters["fixture_kind"] = None
    if rejected:
        parameters["rejected_parameters"] = rejected
    return parameters, rejected


def _fatal(message: str, run_id: str | None = None) -> IngestionFatal:
    run_label = "sem run registrado" if run_id is None else f"run {run_id}"
    print(f"FATAL ({run_label}): {message}", file=sys.stderr)
    return IngestionFatal(message, run_id)


def _rollback(conn: sqlite3.Connection) -> None:
    # Após erro de escrita, a transação implícita bloquearia outros writers.
    try:
        conn.rollback()
    except sqlite3.Error:
        pass


def _effective_max_input_bytes(override: object) -> int:
    if override is None:
        return DEFAULT_MAX_INPUT_BYTES
    if isinstance(override, bool) or not isinstance(override, int) or override < 0:
        raise ValueError(f"max_input_bytes inválido: {override!r}")
    return override


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
