import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * M2: cada servidor gera seu próprio data_root SINTÉTICO (SQLite de ingestão
 * real via `ingest_local_file`) antes de iniciar; nenhum dado real é usado.
 * 3100 → gabarito verificado; 3101 → gabarito não verificado.
 */
function m2Server(port: number, variant: "verified" | "unverified-key") {
  const fixture = join(tmpdir(), "enem-rei-m2-e2e", variant);
  return {
    command:
      `uv run --frozen python tests/e2e/support/build_m2_fixture.py "${fixture}"` +
      ` && npm run start -- --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ENEM_M2_QUESTION_PATH: join(fixture, `question-${variant}.json`),
      ENEM_M2_DATA_ROOT: join(fixture, "data_root"),
    },
  };
}

export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://127.0.0.1:3100" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [m2Server(3100, "verified"), m2Server(3101, "unverified-key")],
});
