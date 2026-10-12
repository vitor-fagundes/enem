"""Armazenamento controlado da ingestão local (SPEC-004)."""

import fcntl
import os
import re
import stat
import threading
from pathlib import Path

import pytest
from enem_rei_ingestion import store
from enem_rei_ingestion.store import (
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


def open_fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


@pytest.fixture
def held_lock(tmp_data_root: Path):
    lock_fd = acquire_writer_lock(tmp_data_root)
    yield lock_fd
    release_writer_lock(lock_fd)


def fd_is_open(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


def test_lock_acquired_on_fresh_data_root(tmp_data_root: Path) -> None:
    lock_fd = acquire_writer_lock(tmp_data_root)
    try:
        assert fd_is_open(lock_fd)
        assert (tmp_data_root / ".ingestion.lock").is_file()
    finally:
        release_writer_lock(lock_fd)


def test_second_lock_fails_while_held(held_lock: int, tmp_data_root: Path) -> None:
    with pytest.raises(WriterLockHeld):
        acquire_writer_lock(tmp_data_root)


def test_second_lock_does_not_block(held_lock: int, tmp_data_root: Path) -> None:
    outcome: list[BaseException] = []

    def attempt() -> None:
        try:
            acquire_writer_lock(tmp_data_root)
        except BaseException as exc:
            outcome.append(exc)

    thread = threading.Thread(target=attempt, daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive(), "segunda aquisição bloqueou"
    assert len(outcome) == 1 and isinstance(outcome[0], WriterLockHeld)


def test_failed_lock_does_not_leak_fd(held_lock: int, tmp_data_root: Path) -> None:
    before = open_fd_count()
    for _ in range(3):
        with pytest.raises(WriterLockHeld):
            acquire_writer_lock(tmp_data_root)
    assert open_fd_count() == before


def test_unexpected_lock_error_closes_fd(
    tmp_data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_flock(fd: int, operation: int) -> None:
        raise OSError("falha simulada")

    monkeypatch.setattr(store.fcntl, "flock", failing_flock)
    before = open_fd_count()
    with pytest.raises(OSError, match="falha simulada"):
        acquire_writer_lock(tmp_data_root)
    assert open_fd_count() == before


def test_lock_release_allows_reacquisition(tmp_data_root: Path) -> None:
    first = acquire_writer_lock(tmp_data_root)
    release_writer_lock(first)
    assert not fd_is_open(first)
    second = acquire_writer_lock(tmp_data_root)
    release_writer_lock(second)


def test_lock_released_after_exception_in_caller(tmp_data_root: Path) -> None:
    lock_fd = acquire_writer_lock(tmp_data_root)
    with pytest.raises(RuntimeError):
        try:
            raise RuntimeError("falha durante o run")
        finally:
            release_writer_lock(lock_fd)
    assert not fd_is_open(lock_fd)
    release_writer_lock(acquire_writer_lock(tmp_data_root))


def test_lock_is_exclusive_flock(held_lock: int, tmp_data_root: Path) -> None:
    other = os.open(tmp_data_root / ".ingestion.lock", os.O_RDONLY)
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(other, fcntl.LOCK_SH | fcntl.LOCK_NB)
    finally:
        os.close(other)


def run_with_timeout(target, timeout: float = 5) -> list[BaseException]:
    """Executa `target` em thread e falha se ele bloquear."""
    errors: list[BaseException] = []

    def wrapper() -> None:
        try:
            target()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    assert not thread.is_alive(), "operação bloqueou"
    return errors


def test_input_regular_file_returns_exact_bytes(synthetic_file) -> None:
    path, _ = synthetic_file(b"conteudo\x00binario")
    with open_validated_input(path) as handle:
        assert handle.read() == b"conteudo\x00binario"


def test_input_regular_file_reads_in_chunks(synthetic_file) -> None:
    path, _ = synthetic_file(b"abcdef")
    with open_validated_input(path) as handle:
        assert handle.read(4) == b"abcd"
        assert handle.read(4) == b"ef"
        assert handle.read(4) == b""


def test_input_symlink_rejected(synthetic_file, tmp_path: Path) -> None:
    target, _ = synthetic_file(b"alvo")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    with pytest.raises(InputRejected, match="link.bin"):
        open_validated_input(link)


def test_input_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(InputRejected, match=str(tmp_path)):
        open_validated_input(tmp_path)


def test_input_fifo_rejected_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "entrada.fifo"
    os.mkfifo(fifo)
    errors = run_with_timeout(lambda: open_validated_input(fifo))
    assert len(errors) == 1 and isinstance(errors[0], InputRejected)
    assert "entrada.fifo" in str(errors[0])


def test_input_character_device_rejected() -> None:
    with pytest.raises(InputRejected, match="/dev/null"):
        open_validated_input("/dev/null")


def test_input_missing_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        open_validated_input(tmp_path / "ausente.bin")


def test_input_rejections_do_not_leak_fds(synthetic_file, tmp_path: Path) -> None:
    target, _ = synthetic_file(b"alvo")
    (tmp_path / "link.bin").symlink_to(target)
    os.mkfifo(tmp_path / "entrada.fifo")
    rejected = [tmp_path / "link.bin", tmp_path, tmp_path / "entrada.fifo"]
    before = open_fd_count()
    for path in rejected:
        with pytest.raises(InputRejected):
            open_validated_input(path)
    with pytest.raises(FileNotFoundError):
        open_validated_input(tmp_path / "ausente.bin")
    assert open_fd_count() == before


def test_input_wrapping_failure_closes_fd(
    synthetic_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = synthetic_file(b"x")

    def failing_fdopen(fd: int, mode: str):
        raise OSError("falha simulada")

    monkeypatch.setattr(store.os, "fdopen", failing_fdopen)
    before = open_fd_count()
    with pytest.raises(OSError, match="falha simulada"):
        open_validated_input(path)
    assert open_fd_count() == before


@pytest.fixture
def empty_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "vazio"
    root.mkdir()
    return root


def assert_fd_is_directory(fd: int, expected: Path) -> None:
    info = os.fstat(fd)
    assert stat.S_ISDIR(info.st_mode)
    expected_info = expected.lstat()
    assert (info.st_dev, info.st_ino) == (expected_info.st_dev, expected_info.st_ino)


def test_anchor_creates_resources_on_empty_data_root(empty_data_root: Path) -> None:
    resources_fd = open_storage_anchor(empty_data_root)
    try:
        assert_fd_is_directory(resources_fd, empty_data_root / "raw" / "resources")
    finally:
        os.close(resources_fd)


def test_anchor_reopens_existing_directories(tmp_data_root: Path) -> None:
    for _ in range(2):
        resources_fd = open_storage_anchor(tmp_data_root)
        try:
            assert_fd_is_directory(resources_fd, tmp_data_root / "raw" / "resources")
        finally:
            os.close(resources_fd)


def test_anchor_rejects_symlink_at_raw(empty_data_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "fora"
    outside.mkdir()
    (empty_data_root / "raw").symlink_to(outside)
    with pytest.raises(UnsafeStoragePath, match="raw"):
        open_storage_anchor(empty_data_root)
    assert list(outside.iterdir()) == []


def test_anchor_rejects_symlink_at_resources(
    empty_data_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "fora"
    outside.mkdir()
    (empty_data_root / "raw").mkdir()
    (empty_data_root / "raw" / "resources").symlink_to(outside)
    with pytest.raises(UnsafeStoragePath, match="resources"):
        open_storage_anchor(empty_data_root)


def test_anchor_rejects_dangling_symlink(empty_data_root: Path, tmp_path: Path) -> None:
    target = tmp_path / "inexistente"
    (empty_data_root / "raw").symlink_to(target)
    with pytest.raises(UnsafeStoragePath, match="raw"):
        open_storage_anchor(empty_data_root)
    assert not target.exists()


def test_anchor_rejects_non_directory_component(empty_data_root: Path) -> None:
    (empty_data_root / "raw").write_bytes(b"")
    with pytest.raises(UnsafeStoragePath, match="raw"):
        open_storage_anchor(empty_data_root)


def test_anchor_does_not_leak_fds(empty_data_root: Path, tmp_path: Path) -> None:
    before = open_fd_count()
    resources_fd = open_storage_anchor(empty_data_root)
    assert open_fd_count() == before + 1
    os.close(resources_fd)

    resources = empty_data_root / "raw" / "resources"
    resources.rmdir()
    resources.symlink_to(tmp_path)
    with pytest.raises(UnsafeStoragePath):
        open_storage_anchor(empty_data_root)
    with pytest.raises(FileNotFoundError):
        open_storage_anchor(tmp_path / "ausente")
    assert open_fd_count() == before


@pytest.fixture
def resources_fd(tmp_data_root: Path):
    fd = open_storage_anchor(tmp_data_root)
    yield fd
    os.close(fd)


def test_temp_file_created_in_resources_and_writable(
    resources_fd: int, tmp_data_root: Path
) -> None:
    tmp_fd, tmp_name = create_temp_file(resources_fd, "run-1")
    try:
        os.write(tmp_fd, b"parcial")
    finally:
        os.close(tmp_fd)
    assert re.fullmatch(r"\.tmp\.run-1\.[0-9a-f]+", tmp_name)
    path = tmp_data_root / "raw" / "resources" / tmp_name
    assert path.read_bytes() == b"parcial"


def test_temp_file_names_are_unique(resources_fd: int) -> None:
    names = set()
    for _ in range(2):
        tmp_fd, tmp_name = create_temp_file(resources_fd, "run-1")
        os.close(tmp_fd)
        names.add(tmp_name)
    assert len(names) == 2


def test_temp_file_never_overwrites_existing(
    resources_fd: int, tmp_data_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store.secrets, "token_hex", lambda nbytes: "abc123")
    existing = tmp_data_root / "raw" / "resources" / ".tmp.run-1.abc123"
    existing.write_bytes(b"original")
    before = open_fd_count()
    with pytest.raises(FileExistsError):
        create_temp_file(resources_fd, "run-1")
    assert open_fd_count() == before
    assert existing.read_bytes() == b"original"


@pytest.mark.parametrize("run_id", ["", "a/b", "../x", "a\0b"])
def test_temp_file_rejects_unsafe_run_id(resources_fd: int, run_id: str) -> None:
    before = open_fd_count()
    with pytest.raises(ValueError):
        create_temp_file(resources_fd, run_id)
    assert open_fd_count() == before


SHA_A = "a" * 64


def stage(resources_fd: int, content: bytes) -> str:
    tmp_fd, tmp_name = create_temp_file(resources_fd, "run-1")
    try:
        os.write(tmp_fd, content)
    finally:
        os.close(tmp_fd)
    return tmp_name


def test_publish_new_payload(resources_fd: int, tmp_data_root: Path) -> None:
    resources = tmp_data_root / "raw" / "resources"
    tmp_name = stage(resources_fd, b"conteudo novo")
    locator = publish_payload(resources_fd, tmp_name, SHA_A)
    assert locator == f"raw/resources/{SHA_A}/payload"
    assert (tmp_data_root / locator).read_bytes() == b"conteudo novo"
    assert not (resources / tmp_name).exists()
    assert [p.name for p in resources.iterdir()] == [SHA_A]


def test_publish_reuses_existing_empty_sha_directory(
    resources_fd: int, tmp_data_root: Path
) -> None:
    (tmp_data_root / "raw" / "resources" / SHA_A).mkdir()
    locator = publish_payload(resources_fd, stage(resources_fd, b"x"), SHA_A)
    assert (tmp_data_root / locator).read_bytes() == b"x"


def test_publish_never_overwrites_existing_payload(
    resources_fd: int, tmp_data_root: Path
) -> None:
    resources = tmp_data_root / "raw" / "resources"
    first = publish_payload(resources_fd, stage(resources_fd, b"original"), SHA_A)
    tmp_name = stage(resources_fd, b"substituto")
    before = open_fd_count()
    with pytest.raises(FileExistsError):
        publish_payload(resources_fd, tmp_name, SHA_A)
    assert open_fd_count() == before
    assert (tmp_data_root / first).read_bytes() == b"original"
    assert (resources / tmp_name).read_bytes() == b"substituto"


def test_publish_rejects_symlinked_sha_directory(
    resources_fd: int, tmp_data_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "fora"
    outside.mkdir()
    resources = tmp_data_root / "raw" / "resources"
    (resources / SHA_A).symlink_to(outside)
    tmp_name = stage(resources_fd, b"x")
    before = open_fd_count()
    with pytest.raises(UnsafeStoragePath, match=SHA_A):
        publish_payload(resources_fd, tmp_name, SHA_A)
    assert open_fd_count() == before
    assert list(outside.iterdir()) == []
    assert (resources / tmp_name).read_bytes() == b"x"


@pytest.mark.parametrize(
    "sha256_hex", ["A" * 64, "a" * 63, "a" * 65, "g" * 64, "../" + "a" * 61, ""]
)
def test_publish_rejects_invalid_sha256(
    resources_fd: int, tmp_data_root: Path, sha256_hex: str
) -> None:
    resources = tmp_data_root / "raw" / "resources"
    tmp_name = stage(resources_fd, b"x")
    with pytest.raises(ValueError):
        publish_payload(resources_fd, tmp_name, sha256_hex)
    assert sorted(p.name for p in resources.iterdir()) == [tmp_name]


def test_publish_keeps_state_when_link_fails(
    resources_fd: int, tmp_data_root: Path
) -> None:
    before = open_fd_count()
    with pytest.raises(FileNotFoundError):
        publish_payload(resources_fd, ".tmp.run-1.ausente", SHA_A)
    assert open_fd_count() == before
    assert not (tmp_data_root / "raw" / "resources" / SHA_A / "payload").exists()


def test_orphan_temps_cleanup_removes_only_stale_temp_files(
    resources_fd: int, tmp_data_root: Path, tmp_path: Path
) -> None:
    resources = tmp_data_root / "raw" / "resources"
    published = publish_payload(resources_fd, stage(resources_fd, b"pub"), SHA_A)
    for name in [".tmp.run-1.aa", ".tmp.run-12.bb", ".tmp.run.cc", ".tmp.run-2.dd"]:
        (resources / name).write_bytes(b"temp")
    (resources / "nao-temporario").write_bytes(b"x")
    (resources / ".tmp.diretorio").mkdir()
    (resources / ".tmp.link").symlink_to(tmp_path)

    removed = clean_orphan_temps(resources_fd, "run-1")

    assert sorted(removed) == [".tmp.run-12.bb", ".tmp.run-2.dd", ".tmp.run.cc"]
    assert sorted(p.name for p in resources.iterdir()) == [
        ".tmp.diretorio",
        ".tmp.link",
        ".tmp.run-1.aa",
        SHA_A,
        "nao-temporario",
    ]
    assert (tmp_data_root / published).read_bytes() == b"pub"
    assert tmp_path.is_dir()


def test_orphan_temps_cleanup_is_repeatable(
    resources_fd: int, tmp_data_root: Path
) -> None:
    (tmp_data_root / "raw" / "resources" / ".tmp.run-0.aa").write_bytes(b"temp")
    assert clean_orphan_temps(resources_fd, "run-1") == [".tmp.run-0.aa"]
    assert clean_orphan_temps(resources_fd, "run-1") == []


def test_orphan_temps_cleanup_rejects_unsafe_run_id(resources_fd: int) -> None:
    with pytest.raises(ValueError):
        clean_orphan_temps(resources_fd, "")
