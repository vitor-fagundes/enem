import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import Database from "better-sqlite3";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { recordAttempt } from "../../src/lib/attempts/record";

// Data root e catálogo do M4 SINTÉTICOS criados pelo pacote de ingestão real.
const BUILDER = resolve(__dirname, "../e2e/support/build_m2_fixture.py");
let workspace: string;
let base: string;

beforeAll(() => {
  workspace = fs.mkdtempSync(join(tmpdir(), "enem-rei-m4-unit-"));
  base = join(workspace, "base");
  execFileSync("uv", ["run", "--frozen", "python", BUILDER, base], {
    stdio: "pipe",
  });
}, 120_000);

afterAll(() => {
  if (workspace) fs.rmSync(workspace, { recursive: true, force: true });
});

const id = (n: number) => `enem-1999-d9-cd9-q${n}`;
const catalogDir = () => join(base, "catalog-m4");
const dataRoot = () => join(base, "data_root");
const fileSha = (dir: string, n: number) =>
  createHash("sha256")
    .update(fs.readFileSync(join(dir, `${id(n)}.json`)))
    .digest("hex");

let dbCounter = 0;
function env(overrides: Record<string, string | undefined> = {}) {
  return {
    ENEM_ATTEMPTS_DB: join(workspace, `attempts-${dbCounter++}.sqlite`),
    ENEM_CATALOG_DIR: catalogDir(),
    ENEM_DATA_ROOT: dataRoot(),
    ENEM_M2_DATA_ROOT: dataRoot(),
    ...overrides,
  };
}

let uuidCounter = 0;
const uuid = () =>
  `00000000-0000-4000-8000-${(uuidCounter++).toString(16).padStart(12, "0")}`;

function submission(n: number, label: string, extra: object = {}) {
  return {
    submission_id: uuid(),
    question_id: id(n),
    question_file_sha256: fileSha(catalogDir(), n),
    selected_label: label,
    duration_ms: 4200,
    ...extra,
  };
}

function rows(path: string) {
  if (!fs.existsSync(path)) return [];
  const db = new Database(path, { readonly: true });
  try {
    return db.prepare("SELECT * FROM attempt ORDER BY id").all() as Array<
      Record<string, unknown>
    >;
  } finally {
    db.close();
  }
}

const NOW = () => new Date("2026-10-14T10:00:00.123Z");

describe("recordAttempt (correction on the server)", () => {
  test("correct answer is graded with the verified key and fully recorded", async () => {
    const e = env();
    const input = submission(7, "A");
    const result = await recordAttempt(input, e, NOW);
    expect(result).toEqual({
      status: "RECORDED",
      attempt: {
        evaluation: "CORRECT",
        selected_label: "A",
        answer_key_value: "A",
        answered_at: "2026-10-14T10:00:00.123Z",
      },
    });
    const [row] = rows(e.ENEM_ATTEMPTS_DB);
    const question = JSON.parse(
      fs.readFileSync(join(catalogDir(), `${id(7)}.json`), "utf8"),
    );
    const [booklet, key] = question.resources;
    expect(row).toEqual({
      id: 1,
      submission_id: input.submission_id,
      question_id: id(7),
      question_file_sha256: input.question_file_sha256,
      question_format: "enem-rei/m2-question/v1",
      area: "Linguagens, Códigos e suas Tecnologias",
      area_code: "LC",
      selected_label: "A",
      evaluation: "CORRECT",
      answer_key_status: "VALID",
      answer_key_value: "A",
      answer_key_resource_id: key.resource_id,
      answer_key_resource_sha256: key.sha256,
      content_resource_sha256: booklet.sha256,
      evaluation_rule_version: "evaluateAnswer/v1",
      answered_at: "2026-10-14T10:00:00.123Z",
      duration_ms: 4200,
    });
  });

  test("client-supplied result, key, area and time are ignored", async () => {
    const e = env();
    const result = await recordAttempt(
      submission(12, "A", {
        evaluation: "CORRECT",
        answer_key: { published_value: "A", status: "VALID" },
        answer_key_value: "A",
        area: "Linguagens, Códigos e suas Tecnologias",
        answered_at: "2000-01-01T00:00:00.000Z",
      }),
      e,
      NOW,
    );
    expect(result.status).toBe("RECORDED");
    if (result.status !== "RECORDED") return;
    expect(result.attempt.evaluation).toBe("INCORRECT");
    expect(result.attempt.answer_key_value).toBe("C");
    expect(rows(e.ENEM_ATTEMPTS_DB)[0]).toMatchObject({
      evaluation: "INCORRECT",
      area_code: "MT",
      answered_at: "2026-10-14T10:00:00.123Z",
    });
  });

  test("multiple attempts of the same question create separate rows", async () => {
    const e = env();
    await recordAttempt(submission(7, "A"), e);
    await recordAttempt(submission(7, "B"), e);
    expect(
      rows(e.ENEM_ATTEMPTS_DB).map((r) => [r.question_id, r.evaluation]),
    ).toEqual([
      [id(7), "CORRECT"],
      [id(7), "INCORRECT"],
    ]);
  });

  test("same submission_id and payload is idempotent; different payload is rejected", async () => {
    const e = env();
    const input = submission(30, "E");
    const first = await recordAttempt(input, e, NOW);
    const later = () => new Date("2026-10-15T00:00:00.000Z");
    const again = await recordAttempt({ ...input }, e, later);
    expect(again).toEqual({ ...first, status: "ALREADY_RECORDED" });
    const conflict = await recordAttempt({ ...input, selected_label: "A" }, e);
    expect(conflict).toMatchObject({
      status: "REJECTED",
      code: "IDEMPOTENCY_CONFLICT",
    });
    const conflictDuration = await recordAttempt(
      { ...input, duration_ms: 1 },
      e,
    );
    expect(conflictDuration).toMatchObject({ code: "IDEMPOTENCY_CONFLICT" });
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(1);
  });

  test("unverified answer key records NOT_VERIFIED without key data", async () => {
    const e = env();
    const result = await recordAttempt(submission(25, "D"), e);
    expect(result).toMatchObject({
      status: "RECORDED",
      attempt: { evaluation: "NOT_VERIFIED", answer_key_value: null },
    });
    expect(rows(e.ENEM_ATTEMPTS_DB)[0]).toMatchObject({
      evaluation: "NOT_VERIFIED",
      area_code: "CN",
      answer_key_status: null,
      answer_key_value: null,
      answer_key_resource_id: null,
      answer_key_resource_sha256: null,
    });
  });

  test("annulled question records ANNULLED", async () => {
    const e = env();
    const result = await recordAttempt(submission(20, "A"), e);
    expect(result).toMatchObject({
      status: "RECORDED",
      attempt: { evaluation: "ANNULLED", answer_key_value: null },
    });
    expect(rows(e.ENEM_ATTEMPTS_DB)[0]).toMatchObject({
      evaluation: "ANNULLED",
      area_code: "CH",
      answer_key_status: "ANNULLED",
      answer_key_value: null,
    });
  });

  test("unmapped area is recorded as observed with a null code", async () => {
    const e = env();
    await recordAttempt(submission(30, "E"), e);
    expect(rows(e.ENEM_ATTEMPTS_DB)[0]).toMatchObject({
      area: "Área Fictícia Três",
      area_code: null,
    });
  });

  test.each<[string, (n: number) => object, number, string]>([
    [
      "unknown question",
      () => ({ question_id: "inexistente" }),
      7,
      "QUESTION_NOT_FOUND",
    ],
    ["blocked question", () => ({}), 35, "QUESTION_BLOCKED"],
    [
      "divergent question version",
      () => ({ question_file_sha256: "0".repeat(64) }),
      7,
      "VERSION_MISMATCH",
    ],
    [
      "invalid alternative",
      () => ({ selected_label: "F" }),
      7,
      "INVALID_SUBMISSION",
    ],
    ["negative duration", () => ({ duration_ms: -1 }), 7, "INVALID_SUBMISSION"],
    [
      "fractional duration",
      () => ({ duration_ms: 1.5 }),
      7,
      "INVALID_SUBMISSION",
    ],
    [
      "duration above 24 h",
      () => ({ duration_ms: 86_400_001 }),
      7,
      "INVALID_SUBMISSION",
    ],
    [
      "missing duration",
      () => ({ duration_ms: undefined }),
      7,
      "INVALID_SUBMISSION",
    ],
    [
      "malformed submission_id",
      () => ({ submission_id: "x" }),
      7,
      "INVALID_SUBMISSION",
    ],
  ])("rejects %s without recording", async (_name, extra, n, code) => {
    const e = env();
    const result = await recordAttempt(submission(n, "A", extra(n)), e);
    expect(result).toMatchObject({ status: "REJECTED", code });
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(0);
  });

  test("question edited between display and submission is rejected", async () => {
    const dir = join(workspace, "catalog-edited");
    fs.cpSync(catalogDir(), dir, { recursive: true });
    const input = {
      ...submission(45, "B"),
      question_file_sha256: fileSha(dir, 45),
    };
    const path = join(dir, `${id(45)}.json`);
    fs.writeFileSync(path, fs.readFileSync(path, "utf8") + "\n");
    const e = env({ ENEM_CATALOG_DIR: dir });
    const result = await recordAttempt(input, e);
    expect(result).toMatchObject({ code: "VERSION_MISMATCH" });
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(0);
    // A versão atual é aceita.
    const ok = await recordAttempt(
      {
        ...input,
        submission_id: uuid(),
        question_file_sha256: fileSha(dir, 45),
      },
      e,
    );
    expect(ok.status).toBe("RECORDED");
  });

  test("question removed from the catalog after display is rejected", async () => {
    const dir = join(workspace, "catalog-removed");
    fs.cpSync(catalogDir(), dir, { recursive: true });
    const input = submission(12, "C");
    fs.rmSync(join(dir, `${id(12)}.json`));
    const e = env({ ENEM_CATALOG_DIR: dir });
    expect(await recordAttempt(input, e)).toMatchObject({
      code: "QUESTION_NOT_FOUND",
    });
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(0);
  });

  test("missing ENEM_ATTEMPTS_DB is an explicit error and creates no database", async () => {
    const before = fs.readdirSync(workspace).sort();
    const ingestion = fs.readFileSync(join(dataRoot(), "ingestion.db"));
    for (const value of [undefined, ""]) {
      const result = await recordAttempt(
        submission(7, "A"),
        env({ ENEM_ATTEMPTS_DB: value }),
      );
      expect(result).toMatchObject({
        status: "REJECTED",
        code: "NOT_CONFIGURED",
        message: expect.stringContaining(
          "Registro de tentativas não configurado",
        ),
      });
    }
    expect(fs.readdirSync(workspace).sort()).toEqual(before);
    expect(
      fs.readFileSync(join(dataRoot(), "ingestion.db")).equals(ingestion),
    ).toBe(true);
  });

  test("refuses the ingestion database and raw/ without writing", async () => {
    const ingestionPath = join(dataRoot(), "ingestion.db");
    const ingestion = fs.readFileSync(ingestionPath);
    for (const path of [ingestionPath, join(dataRoot(), "raw", "x.sqlite")]) {
      const result = await recordAttempt(
        submission(7, "A"),
        env({ ENEM_ATTEMPTS_DB: path }),
      );
      expect(result).toMatchObject({ code: "CONFIG_REFUSED" });
    }
    expect(fs.readFileSync(ingestionPath).equals(ingestion)).toBe(true);
    expect(fs.existsSync(join(dataRoot(), "raw", "x.sqlite"))).toBe(false);
  });

  test("unconfigured catalog is rejected without recording", async () => {
    const e = env({ ENEM_CATALOG_DIR: undefined });
    expect(await recordAttempt(submission(7, "A"), e)).toMatchObject({
      code: "CATALOG_UNAVAILABLE",
    });
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(0);
  });

  test("attempts persist across reopening the database", async () => {
    const e = env();
    await recordAttempt(submission(7, "A"), e);
    await recordAttempt(submission(12, "C"), e);
    expect(rows(e.ENEM_ATTEMPTS_DB)).toHaveLength(2);
    await recordAttempt(submission(7, "D"), e);
    expect(rows(e.ENEM_ATTEMPTS_DB).map((r) => r.evaluation)).toEqual([
      "CORRECT",
      "CORRECT",
      "INCORRECT",
    ]);
  });
});
