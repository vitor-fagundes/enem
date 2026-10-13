# ADR-0002 — Leitura somente leitura do SQLite de ingestão pela aplicação web

Status: aceito em 2026-10-13. Vigora desde o M2 e é estendido ao M3.

## Context

A SPEC-004 define o SQLite de ingestão (`ingestion.db`, no data root) como única fonte de verdade dos metadados operacionais e mantém os payloads no filesystem (FR-019). O M2 (`docs/m2-primeira-questao.md`) e o M3 (`docs/m3-catalogo-questoes.md`) exibem questões curadas que referenciam recursos ingeridos por SHA-256, e a proveniência precisa ser verificada antes da exibição. A ingestão é escrita em Python; a aplicação web é Next.js.

## Decision

A aplicação web (`apps/web`) lê o `ingestion.db` e os payloads em modo somente leitura para verificar a proveniência antes de exibir questões: better-sqlite3 com `readonly: true` e `fileMustExist: true`, e recálculo de SHA-256 do payload em streaming, com conferência de tamanho.

O SQLite continua a única autoridade (SPEC-004 FR-019). A web nunca escreve no banco nem nos payloads e não mantém cópia própria desses metadados. A decisão já está em uso no M2 (`apps/web/src/lib/m2/provenance.ts`) e é estendida ao catálogo do M3.

## Consequences

A verificação usa a autoridade diretamente, sem segunda fonte de verdade nem etapa de exportação. Em contrapartida, a web fica acoplada ao schema da ingestão (Python, `db.py`). Mitigações:

- consultas mínimas, restritas a `source_resource` e `resource_acquisition`;
- testes com fixture gerada pelo próprio pacote Python de ingestão;
- falha explícita de proveniência em caso de divergência, sem exibir a questão afetada como verificada.

Mudanças no schema dessas tabelas exigem revisar as consultas da web e este ADR. O runtime Node no servidor continua necessário (ADR-0001).

## Alternativas consideradas

- Snapshot/export gerado em Python para consumo da web: rejeitado para o MVP por criar um artefato derivado a manter sincronizado, uma etapa extra de execução e o risco de ser tratado como segunda autoridade (FR-019 só admite export identificável como snapshot e derivado).
- Duplicar os dados no banco da web: rejeitado para o MVP por criar segunda autoridade dos metadados de recurso, com duas lógicas de atualização divergentes, contrariando FR-019.
