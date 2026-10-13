"""Hash SHA-256 em streaming com limite de tamanho (SPEC-004, T-007)."""

import hashlib
import io

import pytest
from enem_rei_ingestion.hasher import (
    SizeLimitExceeded,
    stream_copy_hash,
    stream_verify_hash,
)

HELLO_SHA256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
CONTENT_100 = bytes(range(100))


class RecordingReader(io.BytesIO):
    """Registra o tamanho pedido em cada read()."""

    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.requested_sizes: list[int | None] = []

    def read(self, size: int | None = -1) -> bytes:
        self.requested_sizes.append(size)
        return super().read(size)


class RecordingWriter(io.BytesIO):
    """Registra o tamanho de cada write()."""

    def __init__(self) -> None:
        super().__init__()
        self.written_sizes: list[int] = []

    def write(self, data) -> int:
        self.written_sizes.append(len(data))
        return super().write(data)


def test_copy_hash_known_content() -> None:
    dst = io.BytesIO()
    assert stream_copy_hash(io.BytesIO(b"hello world"), dst) == (HELLO_SHA256, 11)
    assert dst.getvalue() == b"hello world"


def test_verify_hash_matches_copy_hash() -> None:
    copied = stream_copy_hash(io.BytesIO(b"hello world"), io.BytesIO())
    assert stream_verify_hash(io.BytesIO(b"hello world")) == copied


def test_empty_input() -> None:
    dst = io.BytesIO()
    assert stream_copy_hash(io.BytesIO(b""), dst) == (EMPTY_SHA256, 0)
    assert dst.getvalue() == b""
    assert stream_verify_hash(io.BytesIO(b"")) == (EMPTY_SHA256, 0)


@pytest.mark.parametrize("chunk_size", [1, 3, 7, 64, 65536])
def test_chunk_size_does_not_change_result(chunk_size: int) -> None:
    expected = (hashlib.sha256(CONTENT_100).hexdigest(), 100)
    dst = io.BytesIO()
    assert stream_copy_hash(io.BytesIO(CONTENT_100), dst, chunk_size=chunk_size) == (
        expected
    )
    assert dst.getvalue() == CONTENT_100
    assert (
        stream_verify_hash(io.BytesIO(CONTENT_100), chunk_size=chunk_size) == expected
    )


def test_copy_reads_and_writes_in_bounded_chunks() -> None:
    src = RecordingReader(CONTENT_100)
    dst = RecordingWriter()
    stream_copy_hash(src, dst, chunk_size=8)
    assert all(size is not None and 0 < size <= 8 for size in src.requested_sizes)
    assert all(size <= 8 for size in dst.written_sizes)
    assert dst.getvalue() == CONTENT_100


def test_verify_reads_in_bounded_chunks() -> None:
    src = RecordingReader(CONTENT_100)
    stream_verify_hash(src, chunk_size=8)
    assert all(size is not None and 0 < size <= 8 for size in src.requested_sizes)


@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
def test_copy_at_exact_limit_succeeds(chunk_size: int) -> None:
    dst = io.BytesIO()
    result = stream_copy_hash(
        io.BytesIO(CONTENT_100), dst, max_bytes=100, chunk_size=chunk_size
    )
    assert result == (hashlib.sha256(CONTENT_100).hexdigest(), 100)
    assert dst.getvalue() == CONTENT_100


@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
def test_verify_at_exact_limit_succeeds(chunk_size: int) -> None:
    result = stream_verify_hash(
        io.BytesIO(CONTENT_100), max_bytes=100, chunk_size=chunk_size
    )
    assert result == (hashlib.sha256(CONTENT_100).hexdigest(), 100)


def test_empty_input_with_zero_limit_succeeds() -> None:
    assert stream_copy_hash(io.BytesIO(b""), io.BytesIO(), max_bytes=0) == (
        EMPTY_SHA256,
        0,
    )
    assert stream_verify_hash(io.BytesIO(b""), max_bytes=0) == (EMPTY_SHA256, 0)


@pytest.mark.parametrize("max_bytes", [50, 99])
@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
def test_copy_over_limit_fails_without_writing_excess(
    max_bytes: int, chunk_size: int
) -> None:
    dst = io.BytesIO()
    with pytest.raises(SizeLimitExceeded):
        stream_copy_hash(
            io.BytesIO(CONTENT_100), dst, max_bytes=max_bytes, chunk_size=chunk_size
        )
    assert len(dst.getvalue()) <= max_bytes
    assert CONTENT_100.startswith(dst.getvalue())


@pytest.mark.parametrize("max_bytes", [50, 99])
@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
def test_verify_over_limit_fails(max_bytes: int, chunk_size: int) -> None:
    with pytest.raises(SizeLimitExceeded):
        stream_verify_hash(
            io.BytesIO(CONTENT_100), max_bytes=max_bytes, chunk_size=chunk_size
        )


def test_over_limit_stops_reading_just_past_limit() -> None:
    src = RecordingReader(CONTENT_100)
    with pytest.raises(SizeLimitExceeded):
        stream_verify_hash(src, max_bytes=10, chunk_size=65536)
    assert src.tell() <= 11


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_rejects_non_positive_chunk_size(chunk_size: int) -> None:
    with pytest.raises(ValueError):
        stream_copy_hash(io.BytesIO(b"x"), io.BytesIO(), chunk_size=chunk_size)
    with pytest.raises(ValueError):
        stream_verify_hash(io.BytesIO(b"x"), chunk_size=chunk_size)


def test_rejects_negative_max_bytes() -> None:
    with pytest.raises(ValueError):
        stream_copy_hash(io.BytesIO(b"x"), io.BytesIO(), max_bytes=-1)
    with pytest.raises(ValueError):
        stream_verify_hash(io.BytesIO(b"x"), max_bytes=-1)
