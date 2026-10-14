import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";
import {
  type FixtureVariant,
  attemptsDb,
  fixtureDir,
} from "./tests/e2e/support/run-dir";

/**
 * M2: cada servidor gera seu próprio data_root SINTÉTICO (SQLite de ingestão
 * real via `ingest_local_file`) antes de iniciar; nenhum dado real é usado.
 * 3100 → gabarito verificado; 3101 → gabarito não verificado.
 * M3: o mesmo data_root sintético serve o catálogo; 3100 usa `catalog/`
 * (três questões válidas + entradas rejeitadas) e 3101 `catalog-compromised/`
 * (gabarito adulterado em uma questão e caderno adulterado em outra).
 * M4: cada servidor tem fixture e banco de tentativas próprios, dentro de um
 * diretório temporário desta execução (`support/run-dir.ts`). 3102 serve
 * `catalog-m4/` com banco de tentativas; 3103 serve o mesmo catálogo SEM
 * `ENEM_ATTEMPTS_DB` (registro não configurado).
 */
function server(
  port: number,
  variant: FixtureVariant,
  question: "verified" | "unverified-key",
  catalog: string,
  withAttempts: boolean,
) {
  const fixture = fixtureDir(variant);
  return {
    command:
      `uv run --frozen python tests/e2e/support/build_m2_fixture.py "${fixture}"` +
      ` && npm run start -- --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ENEM_M2_QUESTION_PATH: join(fixture, `question-${question}.json`),
      ENEM_M2_DATA_ROOT: join(fixture, "data_root"),
      ENEM_CATALOG_DIR: join(fixture, catalog),
      ENEM_DATA_ROOT: join(fixture, "data_root"),
      // Vazio = não configurado, mesmo se definido no ambiente de quem executa.
      ENEM_ATTEMPTS_DB: withAttempts ? attemptsDb(variant) : "",
    },
  };
}

export default defineConfig({
  testDir: "./tests/e2e",
  globalTeardown: "./tests/e2e/support/global-teardown.ts",
  use: { baseURL: "http://127.0.0.1:3100" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    server(3100, "verified", "verified", "catalog", true),
    server(
      3101,
      "unverified-key",
      "unverified-key",
      "catalog-compromised",
      true,
    ),
    server(3102, "m4", "verified", "catalog-m4", true),
    server(3103, "m4-unconfigured", "verified", "catalog-m4", false),
  ],
});
