import { execFileSync } from "node:child_process";
import * as fs from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import {
  afterAll,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from "vitest";
import { loadCatalog, navigableEntries } from "../../src/lib/m3/catalog";

// Espiona a leitura de payloads (recálculo de SHA-256) feita pela verificação
// de proveniência, para contar verificações de recurso por requisição.
vi.mock("node:fs", async (importOriginal) => {
  const original = await importOriginal<typeof import("node:fs")>();
  return { ...original, createReadStream: vi.fn(original.createReadStream) };
});

// Data root e catálogo SINTÉTICOS criados pelo pacote de ingestão real.
const BUILDER = resolve(__dirname, "../e2e/support/build_m2_fixture.py");
let workspace: string;
let base: string;

beforeAll(() => {
  workspace = fs.mkdtempSync(join(tmpdir(), "enem-rei-m3-unit-"));
  base = join(workspace, "base");
  execFileSync("uv", ["run", "--frozen", "python", BUILDER, base], {
    stdio: "pipe",
  });
}, 120_000);

afterAll(() => {
  if (workspace) fs.rmSync(workspace, { recursive: true, force: true });
});

beforeEach(() => {
  vi.mocked(fs.createReadStream).mockClear();
});

const dataRoot = () => join(base, "data_root");
const id = (n: number) => `enem-1999-d9-cd9-q${n}`;

let counter = 0;
function emptyCatalogDir() {
  const dir = join(workspace, `catalog-${counter++}`);
  fs.mkdirSync(dir);
  return dir;
}

describe("loadCatalog", () => {
  test("not configured without both environment paths", async () => {
    expect(await loadCatalog(undefined, undefined)).toEqual({
      status: "NOT_CONFIGURED",
    });
    expect((await loadCatalog(join(base, "catalog"), "")).status).toBe(
      "NOT_CONFIGURED",
    );
    expect((await loadCatalog("", dataRoot())).status).toBe("NOT_CONFIGURED");
  });

  test("missing catalog directory is reported without throwing", async () => {
    const result = await loadCatalog(join(workspace, "nao-existe"), dataRoot());
    expect(result).toEqual({ status: "CATALOG_UNREADABLE", error: "ENOENT" });
  });

  test("lists valid entries in numeric order with verified sources", async () => {
    const result = await loadCatalog(join(base, "catalog"), dataRoot());
    expect(result.status).toBe("READY");
    if (result.status !== "READY") return;
    expect(result.entries.map((e) => e.id)).toEqual([id(7), id(12), id(30)]);
    expect(result.entries.map((e) => e.source)).toEqual([
      "VERIFIED",
      "VERIFIED",
      "VERIFIED",
    ]);
    expect(
      result.entries.map((e) => e.verifiedAnswerKey?.published_value),
    ).toEqual(["A", "C", "E"]);
  });

  test("rejects invalid entries with warnings and ignores non-catalog files", async () => {
    const result = await loadCatalog(join(base, "catalog"), dataRoot());
    if (result.status !== "READY") throw new Error(result.status);
    expect(result.warnings.map((w) => w.fileName)).toEqual([
      "copia-da-50.json",
      `${id(3)}.json`,
      `${id(40)}.json`,
      `${id(50)}.json`,
      `${id(60)}.json`,
      "nome-diferente.json",
      "quebrado.json",
    ]);
    const names = result.warnings.map((w) => w.fileName).join();
    expect(names).not.toMatch(/bak-|notas\.txt|subdiretorio/);
  });

  test("reads only regular *.json files (no symlinks, directories or backups)", async () => {
    const dir = emptyCatalogDir();
    const source = join(base, "catalog", `${id(7)}.json`);
    fs.copyFileSync(source, join(dir, `${id(7)}.json`));
    fs.copyFileSync(source, join(dir, `${id(7)}.json.bak-20000101T000000Z`));
    fs.copyFileSync(source, join(dir, `${id(7)}.txt`));
    fs.symlinkSync(
      join(base, "catalog", `${id(12)}.json`),
      join(dir, `${id(12)}.json`),
    );
    fs.mkdirSync(join(dir, `${id(30)}.json`));
    const result = await loadCatalog(dir, dataRoot());
    if (result.status !== "READY") throw new Error(result.status);
    expect(result.entries.map((e) => e.id)).toEqual([id(7)]);
    expect(result.warnings).toEqual([]);
  });

  test("three questions sharing two PDFs verify exactly two resources", async () => {
    const result = await loadCatalog(join(base, "catalog"), dataRoot());
    if (result.status !== "READY") throw new Error(result.status);
    expect(result.entries).toHaveLength(3);
    const payloadReads = vi
      .mocked(fs.createReadStream)
      .mock.calls.map(([path]) => String(path));
    expect(payloadReads).toHaveLength(2);
    expect(new Set(payloadReads).size).toBe(2);
    for (const path of payloadReads) expect(path).toMatch(/\/payload$/);
  });

  test("no cache between requests: each call verifies again", async () => {
    await loadCatalog(join(base, "catalog"), dataRoot());
    await loadCatalog(join(base, "catalog"), dataRoot());
    expect(vi.mocked(fs.createReadStream)).toHaveBeenCalledTimes(4);
  });

  test("a compromised source only affects the questions that depend on it", async () => {
    const result = await loadCatalog(
      join(base, "catalog-compromised"),
      dataRoot(),
    );
    if (result.status !== "READY") throw new Error(result.status);
    const byId = new Map(result.entries.map((e) => [e.id, e]));
    // Fontes válidas (caderno e gabarito originais).
    expect(byId.get(id(7))!.source).toBe("VERIFIED");
    expect(byId.get(id(7))!.verifiedAnswerKey?.published_value).toBe("A");
    // Só o gabarito adulterado: exibida sem correção.
    expect(byId.get(id(12))!.source).toBe("KEY_UNVERIFIED");
    expect(byId.get(id(12))!.verifiedAnswerKey).toBeNull();
    expect(byId.get(id(12))!.checks.map((c) => c.ok)).toEqual([true, false]);
    // Caderno adulterado: bloqueada, sem gabarito.
    expect(byId.get(id(30))!.source).toBe("BLOCKED");
    expect(byId.get(id(30))!.verifiedAnswerKey).toBeNull();
    expect(byId.get(id(30))!.checks[0]!.problems).toContain(
      "SHA-256 recalculado do payload diverge",
    );
    expect(navigableEntries(result.entries).map((e) => e.id)).toEqual([
      id(7),
      id(12),
    ]);
    // Quatro recursos distintos para três questões: quatro verificações.
    expect(vi.mocked(fs.createReadStream)).toHaveBeenCalledTimes(4);
  });

  test("missing SQLite blocks entries without breaking the catalog", async () => {
    const result = await loadCatalog(
      join(base, "catalog"),
      join(workspace, "data-root-inexistente"),
    );
    if (result.status !== "READY") throw new Error(result.status);
    expect(result.entries.map((e) => e.source)).toEqual([
      "BLOCKED",
      "BLOCKED",
      "BLOCKED",
    ]);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  test("does not write to the SQLite database", async () => {
    const dbPath = join(dataRoot(), "ingestion.db");
    const before = fs.readFileSync(dbPath);
    await loadCatalog(join(base, "catalog"), dataRoot());
    expect(fs.readFileSync(dbPath).equals(before)).toBe(true);
  });
});
