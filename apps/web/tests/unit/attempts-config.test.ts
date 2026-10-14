import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import {
  findRepoDataRaw,
  resolveAttemptsDb,
} from "../../src/lib/attempts/config";

let dir: string;
let dataRoot: string;
let m2Root: string;
let repoRaw: string;

beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), "enem-rei-m4-config-"));
  dataRoot = join(dir, "data_root");
  m2Root = join(dir, "m2_root");
  repoRaw = join(dir, "repo", "data", "raw");
  for (const d of [join(dataRoot, "raw"), join(m2Root, "raw"), repoRaw]) {
    mkdirSync(d, { recursive: true });
  }
  writeFileSync(join(dataRoot, "ingestion.db"), "");
  writeFileSync(join(m2Root, "ingestion.db"), "");
  mkdirSync(join(dir, "local"));
  symlinkSync(join(dataRoot, "ingestion.db"), join(dir, "local", "link.db"));
  symlinkSync(dataRoot, join(dir, "alias-root"));
});

afterAll(() => rmSync(dir, { recursive: true, force: true }));

const env = (ENEM_ATTEMPTS_DB: string | undefined) => ({
  ENEM_ATTEMPTS_DB,
  ENEM_DATA_ROOT: dataRoot,
  ENEM_M2_DATA_ROOT: m2Root,
});
const resolve = (path: string | undefined) =>
  resolveAttemptsDb(env(path), repoRaw);

describe("resolveAttemptsDb", () => {
  test("missing or blank variable is not configured", async () => {
    expect(await resolve(undefined)).toEqual({ status: "NOT_CONFIGURED" });
    expect(await resolve("   ")).toEqual({ status: "NOT_CONFIGURED" });
  });

  test("accepts a new file in an existing directory (not created here)", async () => {
    const path = join(dir, "local", "attempts.sqlite");
    expect(await resolve(path)).toEqual({ status: "OK", path, exists: false });
  });

  test("refuses when the parent directory does not exist", async () => {
    const result = await resolve(join(dir, "nao-existe", "attempts.sqlite"));
    expect(result.status).toBe("REFUSED");
  });

  test("refuses the ingestion database of either data root", async () => {
    for (const path of [
      join(dataRoot, "ingestion.db"),
      join(m2Root, "ingestion.db"),
      join(dataRoot, ".", "raw", "..", "ingestion.db"),
    ]) {
      const result = await resolve(path);
      expect(result.status, path).toBe("REFUSED");
    }
  });

  test("refuses the ingestion database reached through symlinks", async () => {
    for (const path of [
      join(dir, "local", "link.db"),
      join(dir, "alias-root", "ingestion.db"),
    ]) {
      expect((await resolve(path)).status, path).toBe("REFUSED");
    }
  });

  test("refuses paths inside raw/ of a data root or the repository data/raw", async () => {
    for (const path of [
      join(dataRoot, "raw", "attempts.sqlite"),
      join(m2Root, "raw", "attempts.sqlite"),
      join(dir, "alias-root", "raw", "attempts.sqlite"),
      join(repoRaw, "attempts.sqlite"),
    ]) {
      expect((await resolve(path)).status, path).toBe("REFUSED");
    }
  });

  test("refuses a directory", async () => {
    expect((await resolve(join(dir, "local"))).status).toBe("REFUSED");
  });

  test("other files in a data root are accepted", async () => {
    const path = join(dataRoot, "attempts.sqlite");
    expect((await resolve(path)).status).toBe("OK");
  });

  test("finds the repository data/raw from the web app directory", () => {
    expect(findRepoDataRaw()).toMatch(/\/data\/raw$/);
    expect(findRepoDataRaw(join(dir, "repo", "apps", "web"))).toBe(repoRaw);
  });
});
