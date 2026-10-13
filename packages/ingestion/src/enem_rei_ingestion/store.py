"""Armazenamento controlado e exclusividade de escrita da ingestão (SPEC-004)."""

import errno
import fcntl
import os
import re
import secrets
import stat
from typing import BinaryIO

LOCK_FILENAME = ".ingestion.lock"
RESOURCES_PATH = ("raw", "resources")
TEMP_PREFIX = ".tmp."
PAYLOAD_NAME = "payload"
SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class WriterLockHeld(Exception):
    """Outro processo de ingestão já detém o lock de escrita do data root."""


class InputRejected(Exception):
    """A entrada local não é um arquivo regular aceito para cópia segura."""

    def __init__(self, path: str | os.PathLike[str], reason: str) -> None:
        super().__init__(f"entrada rejeitada: {os.fspath(path)}: {reason}")
        self.path = os.fspath(path)
        self.reason = reason


class UnsafeStoragePath(Exception):
    """Componente do armazenamento controlado é link ou não é diretório."""

    def __init__(self, component: str, reason: str) -> None:
        super().__init__(f"armazenamento inseguro: {component}: {reason}")
        self.component = component
        self.reason = reason


def acquire_writer_lock(data_root: str | os.PathLike[str]) -> int:
    """Obtém o lock exclusivo de escrita do data root sem bloquear.

    Retorna o descritor do arquivo de lock; o chamador o mantém durante todo o
    run e o libera com `release_writer_lock` em bloco `finally`. Se o lock já
    estiver ocupado, falha imediatamente com `WriterLockHeld`.

    Limitação: `flock` coordena apenas processos de ingestão cooperantes que
    usam este lock. Não impede acesso de outros processos ao filesystem; a
    proteção do data root contra escrita não confiável depende de permissões.
    """
    lock_fd = os.open(
        os.path.join(data_root, LOCK_FILENAME), os.O_WRONLY | os.O_CREAT, 0o644
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise WriterLockHeld(
            f"outro processo de ingestão detém o lock em {data_root}"
        ) from None
    except BaseException:
        os.close(lock_fd)
        raise
    return lock_fd


def release_writer_lock(lock_fd: int) -> None:
    """Libera o lock e fecha o descritor obtido em `acquire_writer_lock`."""
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def open_validated_input(path: str | os.PathLike[str]) -> BinaryIO:
    """Abre arquivo regular de entrada para leitura em streaming.

    A validação usa o próprio descritor aberto (sem checagem prévia por path):
    `O_NOFOLLOW` rejeita symlink no último componente e `O_NONBLOCK` evita que
    FIFO ou dispositivo bloqueiem antes do `fstat`. Ausência da entrada mantém
    `FileNotFoundError`.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise InputRejected(path, "link simbólico não é aceito") from exc
        raise
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise InputRejected(path, "não é arquivo regular")
        # O_NONBLOCK só servia à abertura; a leitura segue o modo normal.
        fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) & ~os.O_NONBLOCK)
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def open_storage_anchor(data_root: str | os.PathLike[str]) -> int:
    """Abre `<data_root>/raw/resources` como descritor de diretório confiável.

    O data root é resolvido uma única vez; `raw` e `resources` são abertos
    relativos ao descritor do pai com `O_NOFOLLOW`, criados se ausentes, e
    rejeitados se forem symlink ou não forem diretório. Retorna somente o
    descritor de `resources`; o chamador deve fechá-lo.

    Premissa de confiança: a árvore do data root deve ser gravável apenas por
    processos confiáveis, garantido por permissões do filesystem. Descritores
    não impedem que quem tem escrita mova diretórios entre operações, e o
    `flock` de `acquire_writer_lock` coordena apenas writers cooperantes.
    """
    parent_fd = os.open(os.path.realpath(data_root), os.O_RDONLY | os.O_DIRECTORY)
    try:
        for depth, name in enumerate(RESOURCES_PATH):
            component = "/".join(RESOURCES_PATH[: depth + 1])
            child_fd = _open_or_create_directory(parent_fd, name, component)
            os.close(parent_fd)
            parent_fd = child_fd
    except BaseException:
        os.close(parent_fd)
        raise
    return parent_fd


def _open_or_create_directory(parent_fd: int, name: str, component: str) -> int:
    try:
        return _open_directory(parent_fd, name, component)
    except FileNotFoundError:
        pass
    try:
        os.mkdir(name, 0o755, dir_fd=parent_fd)
    except FileExistsError:
        pass  # Criado entre as chamadas; a reabertura abaixo revalida.
    return _open_directory(parent_fd, name, component)


def _open_directory(parent_fd: int, name: str, component: str) -> int:
    try:
        return os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
        )
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise UnsafeStoragePath(
                component, "link simbólico ou não é diretório"
            ) from exc
        raise


def create_temp_file(resources_fd: int, run_id: str) -> tuple[int, str]:
    """Cria `.tmp.<run_id>.<hex aleatório>` em `resources`, sem sobrescrever.

    O temporário fica no mesmo filesystem do destino final e nunca é recurso
    válido (FR-017). O chamador fecha o descritor e publica ou remove o arquivo.
    """
    tmp_name = f"{_run_temp_prefix(run_id)}{secrets.token_hex(8)}"
    tmp_fd = os.open(
        tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=resources_fd
    )
    return tmp_fd, tmp_name


def clean_orphan_temps(resources_fd: int, current_run_id: str) -> list[str]:
    """Remove temporários abandonados em `resources` e retorna os nomes removidos.

    Exige que o chamador detenha o lock exclusivo de escrita. Preserva os
    temporários do run atual (prefixo exato `.tmp.<current_run_id>.`) e só
    remove arquivos regulares com prefixo `.tmp.`; payloads publicados,
    diretórios e links nunca são tocados. Erros de filesystem são propagados.
    """
    current_prefix = _run_temp_prefix(current_run_id)
    removed = []
    with os.scandir(resources_fd) as entries:
        for entry in entries:
            if (
                entry.name.startswith(TEMP_PREFIX)
                and not entry.name.startswith(current_prefix)
                and entry.is_file(follow_symlinks=False)
            ):
                os.unlink(entry.name, dir_fd=resources_fd)
                removed.append(entry.name)
    return removed


def _run_temp_prefix(run_id: str) -> str:
    # run_id compõe o nome do arquivo; não pode sair de `resources`.
    if not run_id or "/" in run_id or "\0" in run_id:
        raise ValueError(f"run_id inválido para nome de temporário: {run_id!r}")
    return f"{TEMP_PREFIX}{run_id}."


def publish_payload(resources_fd: int, tmp_name: str, sha256_hex: str) -> str:
    """Publica o temporário em `<sha256_hex>/payload` sem nunca sobrescrever.

    `os.link` falha com `FileExistsError` se o payload já existir; nesse caso,
    e em qualquer outra falha, o payload existente e o temporário permanecem
    intactos para o chamador decidir. Retorna o storage locator relativo ao
    data root. Não registra nada em SQLite nem revalida payload existente.
    """
    if not SHA256_HEX.fullmatch(sha256_hex):
        raise ValueError(f"sha256 inválido para destino: {sha256_hex!r}")
    try:
        os.mkdir(sha256_hex, 0o755, dir_fd=resources_fd)
    except FileExistsError:
        pass  # Diretório existente é reaberto e validado abaixo.
    locator_dir = "/".join((*RESOURCES_PATH, sha256_hex))
    sha256_fd = _open_directory(resources_fd, sha256_hex, locator_dir)
    try:
        os.link(tmp_name, PAYLOAD_NAME, src_dir_fd=resources_fd, dst_dir_fd=sha256_fd)
    finally:
        os.close(sha256_fd)
    os.unlink(tmp_name, dir_fd=resources_fd)
    return f"{locator_dir}/{PAYLOAD_NAME}"
