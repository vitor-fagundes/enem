"""Fixtures compartilhadas dos testes de ingestão local (SPEC-004).

Somente dados sintéticos pequenos; nada de datasets reais ou downloads.
"""

import hashlib
import io
import sqlite3
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from enem_rei_ingestion.db import ensure_schema, get_connection

# Data fixa para que o mesmo conteúdo gere sempre os mesmos bytes de ZIP.
ZIP_MEMBER_DATE_TIME = (1980, 1, 1, 0, 0, 0)


@pytest.fixture
def tmp_data_root(tmp_path: Path) -> Path:
    """Data root com `raw/resources/`; `.ingestion.lock` não é criado aqui."""
    root = tmp_path / "data"
    (root / "raw" / "resources").mkdir(parents=True)
    return root


@pytest.fixture
def fresh_db(tmp_data_root: Path) -> Iterator[sqlite3.Connection]:
    connection = get_connection(tmp_data_root / "ingestion.db")
    ensure_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def synthetic_file(tmp_path: Path) -> Callable[..., tuple[Path, str]]:
    """Cria arquivo fora do data root e devolve `(caminho, sha256_hex)`."""
    inputs = tmp_path / "inputs"
    inputs.mkdir()

    def create(content: bytes, name: str = "synthetic.bin") -> tuple[Path, str]:
        path = inputs / name
        with path.open("xb") as handle:
            handle.write(content)
        return path, hashlib.sha256(content).hexdigest()

    return create


@pytest.fixture
def synthetic_zip() -> Callable[[dict[str, bytes]], bytes]:
    """Monta ZIP em memória, na ordem dos membros informados, com bytes estáveis."""

    def create(members: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            for name, content in members.items():
                archive.writestr(zipfile.ZipInfo(name, ZIP_MEMBER_DATE_TIME), content)
        return buffer.getvalue()

    return create
