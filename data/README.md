# Política de dados

`raw/` contém originais imutáveis, conforme SPEC-002 §§7–11. Nenhum pipeline pode editar, substituir ou apagar um original. Correções exigem novo arquivo/versão ou nova transformação; preserve o original. Esta fundação documenta a regra; ainda não existe ingestão que a imponha tecnicamente.

`interim/` recebe etapas intermediárias; `processed/` recebe artefatos derivados, preferencialmente Parquet. O banco operacional fica separado, em apps/web/.local/, nunca em raw.

Cada recurso ingerido deverá registrar source_id, provider, source_url, retrieved_at e SHA-256 calculado na aquisição. Transformações registrarão inputs/outputs, versão, timestamp, código, algoritmo e parâmetros, além do relatório de qualidade. O contrato executável aguarda spec própria. Não há manifestos fictícios: nenhuma fonte foi ingerida.

Fontes: Tier A institucional; Tier B derivado; Tier C secundário; Tier D IA identificada. Fontes oficiais têm precedência. Dados de ingresso são observações temporais. Datas ISO 8601, horários UTC e datas sem horário preservadas como tal.

Não baixar grandes datasets nesta etapa. Dados reais, bancos e artefatos são ignorados pelo Git; somente esta política e marcadores de diretórios entram em data/. Fixtures futuras devem ser pequenas, sintéticas e ficar em tests/. Não colocar secrets em dados ou manifestos.
