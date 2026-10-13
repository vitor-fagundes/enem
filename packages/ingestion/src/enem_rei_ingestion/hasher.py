"""SHA-256 em streaming, com contagem de bytes e limite de tamanho (SPEC-004)."""

import hashlib
from collections.abc import Callable
from typing import BinaryIO

DEFAULT_CHUNK_SIZE = 65536


class SizeLimitExceeded(Exception):
    """A entrada ultrapassou `max_bytes`; nenhum byte excedente foi entregue."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"entrada excede o limite de {max_bytes} bytes")
        self.max_bytes = max_bytes


def stream_copy_hash(
    src: BinaryIO,
    dst: BinaryIO,
    max_bytes: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[str, int]:
    """Copia `src` para `dst` calculando SHA-256 e tamanho na mesma leitura."""
    return _stream_hash(src, dst.write, max_bytes, chunk_size)


def stream_verify_hash(
    src: BinaryIO,
    max_bytes: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[str, int]:
    """Calcula SHA-256 e tamanho de `src` sem escrever em lugar algum."""
    return _stream_hash(src, None, max_bytes, chunk_size)


def _stream_hash(
    src: BinaryIO,
    write: Callable[[bytes], object] | None,
    max_bytes: int | None,
    chunk_size: int,
) -> tuple[str, int]:
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser positivo")
    if max_bytes is not None and max_bytes < 0:
        raise ValueError("max_bytes não pode ser negativo")

    digest = hashlib.sha256()
    byte_count = 0
    while True:
        size = chunk_size
        if max_bytes is not None:
            # Lê no máximo um byte além do limite: basta para detectar o excesso.
            size = min(size, max_bytes - byte_count + 1)
        chunk = src.read(size)
        if not chunk:
            return digest.hexdigest(), byte_count
        byte_count += len(chunk)
        if max_bytes is not None and byte_count > max_bytes:
            raise SizeLimitExceeded(max_bytes)
        digest.update(chunk)
        if write is not None:
            write(chunk)
