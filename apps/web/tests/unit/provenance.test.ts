import { execFileSync } from "node:child_process";
import {
  chmodSync,
  cpSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import Database from "better-sqlite3";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import type { CuratedQuestion } from "../../src/domain/question";
import { loadVerifiedQuestion } from "../../src/lib/m2/provenance";

// Data root SINTÉTICO criado pelo pacote de ingestão real (mesmo schema SQLite).
const BUILDER = resolve(__dirname, "../e2e/support/build_m2_fixture.py");
let workspace: string;
let base: string;

beforeAll(() => {
  workspace = mkdtempSync(join(tmpdir(), "enem-rei-m2-unit-"));
  base = join(workspace, "base");
  execFileSync("uv", ["run", "--frozen", "python", BUILDER, base], {
    stdio: "pipe",
  });
}, 120_000);

afterAll(() => {
  if (workspace) rmSync(workspace, { recursive: true, force: true });
});

let counter = 0;
function copyFixture() {
  const dir = join(workspace, `case-${counter++}`);
  cpSync(base, dir, { recursive: true });
  const questionPath = join(dir, "question-verified.json");
  const question = JSON.parse(
    readFileSync(questionPath, "utf8"),
  ) as CuratedQuestion;
  return {
    dataRoot: join(dir, "data_root"),
    questionPath,
    question,
    save: () => writeFileSync(questionPath, JSON.stringify(question)),
    load: () => loadVerifiedQuestion(questionPath, join(dir, "data_root")),
  };
}

describe("loadVerifiedQuestion", () => {
  test("not configured without environment paths", async () => {
    expect(await loadVerifiedQuestion(undefined, undefined)).toEqual({
      status: "NOT_CONFIGURED",
    });
    expect((await loadVerifiedQuestion("x.json", "")).status).toBe(
      "NOT_CONFIGURED",
    );
  });

  test("verifies hashes and exposes the answer key", async () => {
    const fx = copyFixture();
    const result = await fx.load();
    expect(result.status).toBe("READY");
    if (result.status !== "READY") return;
    expect(result.checks.every((check) => check.ok)).toBe(true);
    expect(result.verifiedAnswerKey).toEqual({
      published_value: "B",
      status: "VALID",
    });
  });

  test("does not write to the SQLite database", async () => {
    const fx = copyFixture();
    const dbPath = join(fx.dataRoot, "ingestion.db");
    const before = readFileSync(dbPath);
    await fx.load();
    expect(readFileSync(dbPath).equals(before)).toBe(true);
  });

  test("content sha256 absent from SQLite is a provenance error", async () => {
    const fx = copyFixture();
    fx.question.resources[0]!.sha256 = "0".repeat(64);
    fx.save();
    const result = await fx.load();
    expect(result.status).toBe("PROVENANCE_ERROR");
    if (result.status !== "PROVENANCE_ERROR") return;
    expect(result.checks[0]!.problems).toContain(
      "SHA-256 não registrado em source_resource",
    );
  });

  test("divergent content payload is a provenance error", async () => {
    const fx = copyFixture();
    const sha = fx.question.resources[0]!.sha256;
    const payload = join(fx.dataRoot, "raw/resources", sha, "payload");
    chmodSync(payload, 0o644);
    writeFileSync(payload, "payload sintético adulterado");
    const result = await fx.load();
    expect(result.status).toBe("PROVENANCE_ERROR");
    if (result.status !== "PROVENANCE_ERROR") return;
    expect(result.checks[0]!.problems).toEqual(
      expect.arrayContaining([
        "SHA-256 recalculado do payload diverge",
        "tamanho do payload diverge de byte_size",
      ]),
    );
  });

  test("wrong storage_locator is a provenance error", async () => {
    const fx = copyFixture();
    const db = new Database(join(fx.dataRoot, "ingestion.db"));
    db.prepare(
      "UPDATE source_resource SET storage_locator = ? WHERE id = ?",
    ).run("raw/outro/payload", fx.question.resources[0]!.resource_id);
    db.close();
    const result = await fx.load();
    expect(result.status).toBe("PROVENANCE_ERROR");
  });

  test("missing acquisition for the referenced URL is a provenance error", async () => {
    const fx = copyFixture();
    fx.question.resources[0]!.source_url =
      "https://example.invalid/outra-url.pdf";
    fx.save();
    const result = await fx.load();
    expect(result.status).toBe("PROVENANCE_ERROR");
    if (result.status !== "PROVENANCE_ERROR") return;
    expect(result.checks[0]!.problems).toContain(
      "nenhuma aquisição registrada com a URL referenciada",
    );
  });

  test("resource_id differing from the registered one is a provenance error", async () => {
    const fx = copyFixture();
    const old = fx.question.resources[0]!.resource_id;
    fx.question.resources[0]!.resource_id = "outro-id";
    for (const evidence of fx.question.evidence) {
      if (evidence.locator.resource_id === old)
        evidence.locator.resource_id = "outro-id";
    }
    fx.save();
    expect((await fx.load()).status).toBe("PROVENANCE_ERROR");
  });

  test("answer key failure keeps the question but without verified key", async () => {
    const fx = copyFixture();
    const sha = fx.question.resources[1]!.sha256;
    const payload = join(fx.dataRoot, "raw/resources", sha, "payload");
    chmodSync(payload, 0o644);
    writeFileSync(payload, "gabarito sintético adulterado");
    const result = await fx.load();
    expect(result.status).toBe("READY");
    if (result.status !== "READY") return;
    expect(result.verifiedAnswerKey).toBeNull();
    expect(result.checks[1]!.ok).toBe(false);
  });

  test("missing SQLite database is a provenance error", async () => {
    const fx = copyFixture();
    rmSync(join(fx.dataRoot, "ingestion.db"));
    expect((await fx.load()).status).toBe("PROVENANCE_ERROR");
  });

  test("invalid question file is reported", async () => {
    const fx = copyFixture();
    fx.question.content.alternatives.pop();
    fx.save();
    expect((await fx.load()).status).toBe("INVALID_QUESTION_FILE");
    writeFileSync(fx.questionPath, "{ não é json");
    expect((await fx.load()).status).toBe("INVALID_QUESTION_FILE");
  });
});
