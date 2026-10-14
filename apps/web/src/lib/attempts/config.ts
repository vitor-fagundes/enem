/**
 * Server-side only. Resolução e recusa de `ENEM_ATTEMPTS_DB`
 * (docs/m4-registro-tentativas.md, Decisões; ADR-0003). O banco de tentativas
 * nunca pode coincidir com o `ingestion.db` de um data root configurado nem
 * ficar dentro de `raw/` de um data root ou de `data/raw` do repositório.
 */
import { existsSync, statSync } from "node:fs";
import { realpath, stat } from "node:fs/promises";
import {
  basename,
  dirname,
  isAbsolute,
  join,
  parse,
  relative,
  resolve,
} from "node:path";

export interface AttemptsEnv {
  ENEM_ATTEMPTS_DB?: string | undefined;
  ENEM_DATA_ROOT?: string | undefined;
  ENEM_M2_DATA_ROOT?: string | undefined;
}

export type AttemptsDbConfig =
  | { status: "NOT_CONFIGURED" }
  | { status: "REFUSED"; reason: string }
  | { status: "OK"; path: string; exists: boolean };

/** `data/raw` do repositório: primeiro encontrado subindo a partir de `cwd`. */
export function findRepoDataRaw(start = process.cwd()): string | null {
  let dir = resolve(start);
  const { root } = parse(dir);
  for (;;) {
    const candidate = join(dir, "data", "raw");
    try {
      if (statSync(candidate).isDirectory()) return candidate;
    } catch {
      // continua subindo
    }
    if (dir === root) return null;
    dir = dirname(dir);
  }
}

/** `realpath` quando existe; senão o caminho absoluto resolvido. */
async function canonical(path: string): Promise<string> {
  const absolute = resolve(path);
  try {
    return await realpath(absolute);
  } catch {
    return absolute;
  }
}

function isInside(dir: string, path: string): boolean {
  const rel = relative(dir, path);
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

export async function resolveAttemptsDb(
  env: AttemptsEnv,
  repoDataRaw: string | null = findRepoDataRaw(),
): Promise<AttemptsDbConfig> {
  const configured = env.ENEM_ATTEMPTS_DB?.trim();
  if (!configured) return { status: "NOT_CONFIGURED" };

  const absolute = resolve(configured);
  let parent: string;
  try {
    parent = await realpath(dirname(absolute));
  } catch {
    return {
      status: "REFUSED",
      reason: "o diretório pai de ENEM_ATTEMPTS_DB não existe",
    };
  }
  let path = join(parent, basename(absolute));
  const exists = existsSync(path);
  if (exists) {
    path = await realpath(path);
    if (!(await stat(path)).isFile()) {
      return {
        status: "REFUSED",
        reason: "ENEM_ATTEMPTS_DB não é um arquivo regular",
      };
    }
  }

  const roots = [env.ENEM_DATA_ROOT, env.ENEM_M2_DATA_ROOT]
    .map((root) => root?.trim())
    .filter((root): root is string => Boolean(root));
  for (const root of roots) {
    const rootPath = await canonical(root);
    const ingestion = await canonical(join(rootPath, "ingestion.db"));
    if (path === ingestion || path === join(rootPath, "ingestion.db")) {
      return {
        status: "REFUSED",
        reason: "ENEM_ATTEMPTS_DB não pode ser o banco de ingestão",
      };
    }
    const raw = await canonical(join(rootPath, "raw"));
    if (isInside(raw, path) || isInside(join(rootPath, "raw"), path)) {
      return {
        status: "REFUSED",
        reason: "ENEM_ATTEMPTS_DB não pode ficar dentro de raw/",
      };
    }
  }
  if (repoDataRaw !== null) {
    const raw = await canonical(repoDataRaw);
    if (isInside(raw, path)) {
      return {
        status: "REFUSED",
        reason: "ENEM_ATTEMPTS_DB não pode ficar dentro de data/raw",
      };
    }
  }
  return { status: "OK", path, exists };
}
