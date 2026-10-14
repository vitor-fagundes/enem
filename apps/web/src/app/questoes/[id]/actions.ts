"use server";

import {
  type RecordAttemptResult,
  recordAttempt,
} from "../../../lib/attempts/record";

/**
 * Server Action do M4: corrige no servidor e registra a tentativa
 * (docs/m4-registro-tentativas.md). O argumento vem do navegador e é tratado
 * como não confiável; só `submission_id`, `question_id`,
 * `question_file_sha256`, `selected_label` e `duration_ms` são lidos.
 */
export async function submitAttempt(
  input: unknown,
): Promise<RecordAttemptResult> {
  return recordAttempt(input, {
    ENEM_ATTEMPTS_DB: process.env.ENEM_ATTEMPTS_DB,
    ENEM_CATALOG_DIR: process.env.ENEM_CATALOG_DIR,
    ENEM_DATA_ROOT: process.env.ENEM_DATA_ROOT,
    ENEM_M2_DATA_ROOT: process.env.ENEM_M2_DATA_ROOT,
  });
}
