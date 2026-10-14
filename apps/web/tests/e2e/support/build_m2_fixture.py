"""Gera um data_root SINTÉTICO para o e2e do M2 (docs/m2-primeira-questao.md).

Uso: python build_m2_fixture.py <diretório de saída>

Ingere dois payloads sintéticos com `ingest_local_file` (SPEC-004), reutilizando
o schema real do SQLite de ingestão, e grava dois arquivos de questão fictícios:
`question-verified.json` (gabarito verificável, com confirmação pessoal
registrada) e `question-unverified-key.json` (evidência de gabarito aponta para
SHA-256 não registrado; sem confirmação pessoal registrada). Nenhum dado real.

Para o M3 (docs/m3-catalogo-questoes.md) grava também:
- `catalog/`: três questões fictícias válidas e confirmadas (7, 12 e 30) que
  compartilham os mesmos dois PDFs sintéticos, mais entradas que devem ser
  rejeitadas com aviso (JSON malformado, estrutura inválida, sem confirmação,
  nome diferente do ID, posição duplicada, contexto ENGLISH) ou ignoradas
  (backup `.bak-*`, arquivo não JSON, diretório `*.json`);
- `catalog-compromised/`: as mesmas três posições, mas a 12 usa um gabarito
  sintético adulterado e a 30 um caderno sintético adulterado (payloads
  alterados após a ingestão), para testar falhas de proveniência isoladas.

Para o M4 (docs/m4-registro-tentativas.md) grava `catalog-m4/`, com áreas
oficiais e não mapeadas: 7 (LC, gabarito A), 12 (MT, C), 20 (CH, anulada),
25 (CN, gabarito adulterado: não verificado), 30 (área fictícia, E),
35 (caderno adulterado: bloqueada) e 45 (área fictícia, B; reservada ao teste
de questão alterada entre exibição e envio).
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
BOOKLET_B_URL = "https://example.invalid/sintetico/caderno-b-ficticio.pdf"
KEY_B_URL = "https://example.invalid/sintetico/gabarito-b-ficticio.pdf"


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


def question(
    booklet: dict,
    key: dict,
    confirmation_recorded_at: str | None,
    *,
    number: int = 99,
    area: str = "Área Fictícia de Teste",
    statement: str = "Enunciado sintético de teste: escolha a opção certa",
    key_value: str = "B",
    numbering_context: str = "COMMON",
) -> dict:
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
            "numbering_context": numbering_context,
            "question_number": number,
            "area": area,
        },
        "resources": [booklet, key],
        "content": {
            "base_text": [
                "Parágrafo sintético um, criado apenas para teste automatizado.",
                "Parágrafo sintético dois, sem relação com qualquer prova real.",
            ],
            "source_lines": ["AUTOR FICTÍCIO. Fonte inventada.", "Linha dois."],
            "statement": statement,
            "alternatives": [
                {"label": label, "text": f"opção fictícia {label.lower()}"}
                for label in "ABCDE"
            ],
        },
        "answer_key": {"published_value": key_value, "status": "VALID"},
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


CONFIRMED_AT = "2000-01-02T00:00:00Z"
# (número, área, letra do gabarito) das questões fictícias válidas do catálogo.
CATALOG_QUESTIONS = [
    (7, "Área Fictícia Um", "A"),
    (12, "Área Fictícia Dois", "C"),
    (30, "Área Fictícia Três", "E"),
]


def catalog_id(number: int) -> str:
    return f"enem-1999-d9-cd9-q{number}"


def catalog_question(
    booklet: dict, key: dict, number: int, area: str, letter: str, **kw
) -> dict:
    return question(
        booklet,
        key,
        kw.pop("confirmation_recorded_at", CONFIRMED_AT),
        number=number,
        area=area,
        statement=f"Enunciado sintético da questão fictícia {number}",
        key_value=letter,
        **kw,
    )


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def build_catalog(directory: Path, booklet: dict, key: dict) -> None:
    directory.mkdir()
    valid = {
        n: catalog_question(booklet, key, n, a, k) for n, a, k in CATALOG_QUESTIONS
    }
    for number, data in valid.items():
        write_json(directory / f"{catalog_id(number)}.json", data)
    # Ignorados sem aviso: backup (seria duplicata da 7 se lido), não JSON e diretório.
    write_json(directory / f"{catalog_id(7)}.json.bak-20000101T000000Z", valid[7])
    (directory / "notas.txt").write_text("arquivo fictício que não é JSON")
    (directory / "subdiretorio.json").mkdir()
    # Rejeitados com aviso.
    (directory / "quebrado.json").write_text("{ json sintético quebrado")
    invalid = catalog_question(booklet, key, 60, "Área Fictícia", "A")
    invalid["content"]["alternatives"].pop()
    write_json(directory / f"{catalog_id(60)}.json", invalid)
    write_json(
        directory / f"{catalog_id(40)}.json",
        catalog_question(
            booklet, key, 40, "Área Fictícia", "A", confirmation_recorded_at=None
        ),
    )
    write_json(
        directory / "nome-diferente.json",
        catalog_question(booklet, key, 41, "Área Fictícia", "A"),
    )
    duplicate = catalog_question(booklet, key, 50, "Área Fictícia", "A")
    write_json(directory / f"{catalog_id(50)}.json", duplicate)
    write_json(directory / "copia-da-50.json", duplicate)
    write_json(
        directory / f"{catalog_id(3)}.json",
        catalog_question(
            booklet, key, 3, "Área Fictícia", "A", numbering_context="ENGLISH"
        ),
    )


def tamper(data_root: Path, sha256: str) -> None:
    payload = data_root / "raw/resources" / sha256 / "payload"
    payload.chmod(0o644)
    payload.write_bytes(b"payload sintetico adulterado apos a ingestao\n")


def build_compromised_catalog(
    directory: Path, data_root: Path, inputs: Path, booklet: dict, key: dict
) -> tuple[dict, dict]:
    booklet_b_file = inputs / "caderno-b-ficticio.pdf"
    booklet_b_file.write_bytes(b"%PDF-sintetico caderno B ficticio enem-rei m3\n")
    key_b_file = inputs / "gabarito-b-ficticio.pdf"
    key_b_file.write_bytes(b"%PDF-sintetico gabarito B ficticio enem-rei m3\n")
    booklet_b_id, booklet_b_sha = ingest(data_root, booklet_b_file, BOOKLET_B_URL)
    key_b_id, key_b_sha = ingest(data_root, key_b_file, KEY_B_URL)
    tamper(data_root, booklet_b_sha)
    tamper(data_root, key_b_sha)
    booklet_b = {
        "resource_id": booklet_b_id,
        "sha256": booklet_b_sha,
        "source_url": BOOKLET_B_URL,
    }
    key_b = {"resource_id": key_b_id, "sha256": key_b_sha, "source_url": KEY_B_URL}
    build_compromised_entries(directory, booklet, key, booklet_b, key_b)
    return booklet_b, key_b


def build_compromised_entries(
    directory: Path, booklet: dict, key: dict, booklet_b: dict, key_b: dict
) -> None:
    directory.mkdir()
    sources = {7: (booklet, key), 12: (booklet, key_b), 30: (booklet_b, key)}
    for number, area, letter in CATALOG_QUESTIONS:
        source_booklet, source_key = sources[number]
        write_json(
            directory / f"{catalog_id(number)}.json",
            catalog_question(source_booklet, source_key, number, area, letter),
        )


LC = "Linguagens, Códigos e suas Tecnologias"
CH = "Ciências Humanas e suas Tecnologias"
CN = "Ciências da Natureza e suas Tecnologias"
MT = "Matemática e suas Tecnologias"


def build_m4_catalog(
    directory: Path, booklet: dict, key: dict, booklet_b: dict, key_b: dict
) -> None:
    directory.mkdir()
    entries = {
        7: catalog_question(booklet, key, 7, LC, "A"),
        12: catalog_question(booklet, key, 12, MT, "C"),
        20: catalog_question(booklet, key, 20, CH, "A"),
        25: catalog_question(booklet, key_b, 25, CN, "D"),
        30: catalog_question(booklet, key, 30, "Área Fictícia Três", "E"),
        35: catalog_question(booklet_b, key, 35, "Área Fictícia Bloqueada", "A"),
        45: catalog_question(booklet, key, 45, "Área Fictícia Alterável", "B"),
    }
    entries[20]["answer_key"] = {"published_value": None, "status": "ANNULLED"}
    for number, data in entries.items():
        write_json(directory / f"{catalog_id(number)}.json", data)


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
    build_catalog(out / "catalog", booklet, key)
    booklet_b, key_b = build_compromised_catalog(
        out / "catalog-compromised", data_root, inputs, booklet, key
    )
    build_m4_catalog(out / "catalog-m4", booklet, key, booklet_b, key_b)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
