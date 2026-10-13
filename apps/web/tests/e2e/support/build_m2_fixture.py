"""Gera um data_root SINTÉTICO para o e2e do M2 (docs/m2-primeira-questao.md).

Uso: python build_m2_fixture.py <diretório de saída>

Ingere dois payloads sintéticos com `ingest_local_file` (SPEC-004), reutilizando
o schema real do SQLite de ingestão, e grava dois arquivos de questão fictícios:
`question-verified.json` (gabarito verificável, com confirmação pessoal
registrada) e `question-unverified-key.json` (evidência de gabarito aponta para
SHA-256 não registrado; sem confirmação pessoal registrada). Nenhum dado real.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "packages/ingestion/src"))

from enem_rei_ingestion.ingest import ingest_local_file  # noqa: E402

BOOKLET_URL = "https://example.invalid/sintetico/caderno-ficticio.pdf"
KEY_URL = "https://example.invalid/sintetico/gabarito-ficticio.pdf"


def ingest(data_root: Path, path: Path, url: str) -> tuple[str, str]:
    report = ingest_local_file(
        data_root / "ingestion.db",
        data_root,
        path,
        source_definition_id="DS-SINTETICO",
        source_url=url,
        provider="FIXTURE",
        fixture_kind="SYNTHETIC",
    )
    resource_id = report["units"][0]["resource_id"]
    if report["status"] != "SUCCESS" or resource_id is None:
        raise SystemExit(f"ingestão sintética falhou: {report}")
    return resource_id, hashlib.sha256(path.read_bytes()).hexdigest()


def question(booklet: dict, key: dict, confirmation_recorded_at: str | None) -> dict:
    extraction = {
        "method": "fixture sintética de teste",
        "verified_by": "fixture",
        "verified_at": None,
    }
    if confirmation_recorded_at is not None:
        extraction["confirmation_recorded_at"] = confirmation_recorded_at
    return {
        "format": "enem-rei/m2-question/v1",
        "identification": {
            "edition_year": 1999,
            "application": "Aplicação Fictícia",
            "day": 9,
            "booklet": {"number": 9, "color": "Cor Fictícia"},
            "numbering_context": "COMMON",
            "question_number": 99,
            "area": "Área Fictícia de Teste",
        },
        "resources": [booklet, key],
        "content": {
            "base_text": [
                "Parágrafo sintético um, criado apenas para teste automatizado.",
                "Parágrafo sintético dois, sem relação com qualquer prova real.",
            ],
            "source_lines": ["AUTOR FICTÍCIO. Fonte inventada.", "Linha dois."],
            "statement": "Enunciado sintético de teste: escolha a opção certa",
            "alternatives": [
                {"label": label, "text": f"opção fictícia {label.lower()}"}
                for label in "ABCDE"
            ],
        },
        "answer_key": {"published_value": "B", "status": "VALID"},
        "evidence": [
            {
                "locator": {
                    "resource_id": resource["resource_id"],
                    "locator_type": "PDF_PAGE",
                    "locator_value": {"page_index": page},
                },
                "evidence_role": role,
                "notes": None,
            }
            for role, resource, page in [
                ("CONTENT", booklet, 2),
                ("PLACEMENT", booklet, 2),
                ("ANSWER_KEY", key, 0),
            ]
        ],
        "extraction": extraction,
    }


def main(out: Path) -> None:
    shutil.rmtree(out, ignore_errors=True)
    inputs = out / "inputs"
    data_root = out / "data_root"
    inputs.mkdir(parents=True)
    data_root.mkdir()
    booklet_file = inputs / "caderno-ficticio.pdf"
    booklet_file.write_bytes(b"%PDF-sintetico caderno ficticio enem-rei m2\n")
    key_file = inputs / "gabarito-ficticio.pdf"
    key_file.write_bytes(b"%PDF-sintetico gabarito ficticio enem-rei m2\n")

    booklet_id, booklet_sha = ingest(data_root, booklet_file, BOOKLET_URL)
    key_id, key_sha = ingest(data_root, key_file, KEY_URL)
    booklet = {
        "resource_id": booklet_id,
        "sha256": booklet_sha,
        "source_url": BOOKLET_URL,
    }
    key = {"resource_id": key_id, "sha256": key_sha, "source_url": KEY_URL}
    unregistered_key = {
        "resource_id": "recurso-nao-ingerido",
        "sha256": hashlib.sha256(b"payload sintetico nao ingerido").hexdigest(),
        "source_url": KEY_URL,
    }
    for name, data in [
        ("question-verified.json", question(booklet, key, "2000-01-02T00:00:00Z")),
        ("question-unverified-key.json", question(booklet, unregistered_key, None)),
    ]:
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
