import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * Diretório temporário desta execução do e2e, criado uma vez pelo processo
 * principal do Playwright e herdado pelos workers via variável de ambiente.
 * Cada servidor tem sua própria fixture (recriada ao iniciar) e seu próprio
 * banco de tentativas dentro dele; nada é compartilhado entre execuções.
 */
export const RUN_DIR_PREFIX = join(tmpdir(), "enem-rei-e2e-");

export function e2eRunDir(): string {
  process.env.ENEM_E2E_RUN_DIR ??= mkdtempSync(RUN_DIR_PREFIX);
  return process.env.ENEM_E2E_RUN_DIR;
}

export type FixtureVariant =
  "verified" | "unverified-key" | "m4" | "m4-unconfigured";

export const fixtureDir = (variant: FixtureVariant) =>
  join(e2eRunDir(), variant);

/** Fora do diretório da fixture, que o gerador apaga ao recriar. */
export const attemptsDb = (variant: FixtureVariant) =>
  join(e2eRunDir(), `attempts-${variant}.sqlite`);
