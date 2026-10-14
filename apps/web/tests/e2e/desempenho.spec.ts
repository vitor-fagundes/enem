import { type ChildProcess, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import Database from "better-sqlite3";
import { expect, type Page, test } from "@playwright/test";
import { attemptsDb, fixtureDir } from "./support/run-dir";

// M4 (docs/m4-registro-tentativas.md). Catálogo sintético `catalog-m4/` gerado
// por tests/e2e/support/build_m2_fixture.py:
// 7 (LC, A), 12 (MT, C), 20 (CH, anulada), 25 (CN, gabarito não verificado),
// 30 (área fictícia, E), 35 (bloqueada) e 45 (alterada durante o teste).
// 3102: com banco de tentativas próprio; 3103: sem ENEM_ATTEMPTS_DB.
const M4 = "http://127.0.0.1:3102";
const UNCONFIGURED = "http://127.0.0.1:3103";
const RESTART_PORT = 3104;
const id = (n: number) => `enem-1999-d9-cd9-q${n}`;
const DB = attemptsDb("m4");
const CATALOG = join(fixtureDir("m4"), "catalog-m4");

const confirm = (page: Page) =>
  page.getByRole("button", { name: /Confirmar|Registrando/ });

async function choose(page: Page, label: string) {
  await page.getByRole("radio", { name: new RegExp(`^${label} `) }).check();
}

async function answer(page: Page, label: string) {
  await choose(page, label);
  await confirm(page).click();
}

type Row = Record<string, unknown>;
function rows(path = DB): Row[] {
  if (!existsSync(path)) return [];
  const db = new Database(path, { readonly: true, fileMustExist: true });
  try {
    return db.prepare("SELECT * FROM attempt ORDER BY id").all() as Row[];
  } finally {
    db.close();
  }
}

const sha256 = (path: string) =>
  createHash("sha256").update(readFileSync(path)).digest("hex");

async function expectIndicators(
  page: Page,
  expected: Record<string, string>,
): Promise<void> {
  for (const [key, value] of Object.entries(expected)) {
    await expect(page.getByTestId(`indicator-${key}`)).toHaveText(value);
  }
}

const FINAL_INDICATORS = {
  total: "5",
  correct: "2",
  incorrect: "1",
  "not-corrected": "2",
  rate: "66,7% (2/3)",
};
const FINAL_AREAS = [
  [
    "LC — Linguagens, Códigos e suas Tecnologias",
    "2",
    "1",
    "1",
    "0",
    "50,0% (1/2)",
  ],
  ["CH — Ciências Humanas e suas Tecnologias", "1", "0", "0", "1", "sem dados"],
  [
    "CN — Ciências da Natureza e suas Tecnologias",
    "1",
    "0",
    "0",
    "1",
    "sem dados",
  ],
  ["MT — Matemática e suas Tecnologias", "0", "0", "0", "0", "sem dados"],
  ["Área não mapeada: Área Fictícia Três", "1", "1", "0", "0", "100,0% (1/1)"],
];

async function expectFinalReport(page: Page) {
  await expectIndicators(page, FINAL_INDICATORS);
  const areas = page.getByTestId("area-row");
  await expect(areas).toHaveCount(FINAL_AREAS.length);
  for (const [i, cells] of FINAL_AREAS.entries()) {
    await expect(areas.nth(i).getByRole("cell")).toHaveText(cells);
  }
  const attempts = page.getByTestId("attempt-row");
  await expect(attempts).toHaveCount(5);
  // Mais recente primeiro.
  const expectedOrder = [
    [id(30), "E", "Correto"],
    [id(25), "D", "Não corrigida (gabarito não verificado)"],
    [id(20), "A", "Não corrigida (questão anulada)"],
    [id(7), "B", "Incorreto"],
    [id(7), "A", "Correto"],
  ];
  for (const [i, [question, label, result]] of expectedOrder.entries()) {
    const cells = attempts.nth(i).getByRole("cell");
    await expect(cells.nth(0)).toHaveText(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
    );
    await expect(cells.nth(1)).toHaveText(question!);
    await expect(cells.nth(2)).toHaveText(label!);
    await expect(cells.nth(3)).toHaveText(result!);
    await expect(cells.nth(4)).toHaveText(/^\d+,\d s$/);
  }
  await expect(page.getByText(/não representa domínio/)).toBeVisible();
}

test.describe("M4: attempts are recorded and summarized", () => {
  test.describe.configure({ mode: "serial" });

  test("home links to /desempenho", async ({ page }) => {
    await page.goto(`${M4}/`);
    await page.getByRole("link", { name: "Desempenho (M4)" }).click();
    await expect(page).toHaveURL(/\/desempenho$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Desempenho",
    );
  });

  test("empty history shows no data and reading does not create the database", async ({
    page,
  }) => {
    await page.goto(`${M4}/desempenho`);
    await expectIndicators(page, {
      total: "0",
      correct: "0",
      incorrect: "0",
      "not-corrected": "0",
      rate: "sem dados",
    });
    const areas = page.getByTestId("area-row");
    await expect(areas).toHaveCount(4);
    for (let i = 0; i < 4; i++) {
      await expect(areas.nth(i).getByRole("cell").last()).toHaveText(
        "sem dados",
      );
    }
    await expect(page.getByText("Nenhuma tentativa registrada.")).toBeVisible();
    expect(existsSync(DB)).toBe(false);
  });

  test("the catalog page does not send the answer key to the browser", async ({
    request,
    page,
  }) => {
    const url = `${M4}/questoes/${id(7)}`;
    const html = await (await request.get(url)).text();
    const rsc = await request.get(url, { headers: { RSC: "1" } });
    expect(rsc.headers()["content-type"]).toContain("text/x-component");
    const flight = await rsc.text();
    for (const body of [html, flight]) {
      expect(body).toContain("Enunciado sintético da questão fictícia 7");
      expect(body).not.toContain("published_value");
      expect(body).not.toContain("answer_key");
      expect(body).not.toContain("Gabarito oficial");
    }
    await page.goto(url);
    await expect(page.getByRole("radio")).toHaveCount(5);
    expect(await page.content()).not.toContain("published_value");
    // Controle positivo: o M2 (/questao) ainda envia o gabarito ao navegador.
    expect(await (await request.get(`${M4}/questao`)).text()).toContain(
      "published_value",
    );
  });

  test("confirming records exactly one attempt, corrected on the server", async ({
    page,
  }) => {
    await page.goto(`${M4}/questoes/${id(7)}`);
    await expect(confirm(page)).toBeDisabled();
    await choose(page, "A");
    // Clique duplo: o botão fica indisponível durante o envio.
    await confirm(page).dblclick();
    await expect(page.getByTestId("answer-result")).toHaveText("Correto");
    await expect(page.getByText("Sua resposta: A")).toBeVisible();
    await expect(page.getByText("Gabarito oficial: A")).toBeVisible();
    await expect(page.getByText(/Tentativa registrada em/)).toBeVisible();
    await expect(confirm(page)).toBeDisabled();

    const all = rows();
    expect(all).toHaveLength(1);
    expect(all[0]).toMatchObject({
      question_id: id(7),
      question_file_sha256: sha256(join(CATALOG, `${id(7)}.json`)),
      question_format: "enem-rei/m2-question/v1",
      area: "Linguagens, Códigos e suas Tecnologias",
      area_code: "LC",
      selected_label: "A",
      evaluation: "CORRECT",
      answer_key_status: "VALID",
      answer_key_value: "A",
      evaluation_rule_version: "evaluateAnswer/v1",
    });
    expect(all[0]!.submission_id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(all[0]!.answered_at).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/,
    );
    expect(Number.isInteger(all[0]!.duration_ms)).toBe(true);
    expect(all[0]!.duration_ms as number).toBeGreaterThanOrEqual(0);
  });

  test("answering again after reloading records another attempt", async ({
    page,
  }) => {
    await page.goto(`${M4}/questoes/${id(7)}`);
    await expect(page.getByTestId("answer-result")).toHaveCount(0);
    await answer(page, "B");
    await expect(page.getByTestId("answer-result")).toHaveText("Incorreto");
    await expect(page.getByText("Gabarito oficial: A")).toBeVisible();
    // "Responder novamente" recarrega a página: novo formulário, sem resposta.
    await page.getByRole("button", { name: "Responder novamente" }).click();
    await expect(page.getByTestId("answer-result")).toHaveCount(0);
    await expect(confirm(page)).toBeDisabled();
    expect(
      rows().map((r) => [r.question_id, r.selected_label, r.evaluation]),
    ).toEqual([
      [id(7), "A", "CORRECT"],
      [id(7), "B", "INCORRECT"],
    ]);
    const ids = new Set(rows().map((r) => r.submission_id));
    expect(ids.size).toBe(2);
  });

  test("annulled question is recorded as ANNULLED without correction", async ({
    page,
  }) => {
    await page.goto(`${M4}/questoes/${id(20)}`);
    await answer(page, "A");
    await expect(page.getByTestId("answer-result")).toHaveText(
      "Questão anulada: não há correção.",
    );
    await expect(page.getByText(/Gabarito oficial:/)).toHaveCount(0);
    expect(rows().at(-1)).toMatchObject({
      question_id: id(20),
      evaluation: "ANNULLED",
      answer_key_status: "ANNULLED",
      area_code: "CH",
    });
  });

  test("unverified answer key is recorded as NOT_VERIFIED without correction", async ({
    page,
  }) => {
    await page.goto(`${M4}/questoes/${id(25)}`);
    await expect(
      page.getByText(/gabarito não verificado/i).first(),
    ).toBeVisible();
    await answer(page, "D");
    await expect(page.getByTestId("answer-result")).toHaveText(
      "Sem correção: gabarito não verificado.",
    );
    await expect(page.getByText(/Gabarito oficial:/)).toHaveCount(0);
    expect(rows().at(-1)).toMatchObject({
      question_id: id(25),
      evaluation: "NOT_VERIFIED",
      answer_key_status: null,
      answer_key_value: null,
      area_code: "CN",
    });
  });

  test("unmapped area is recorded with the observed text", async ({ page }) => {
    await page.goto(`${M4}/questoes/${id(30)}`);
    await answer(page, "E");
    await expect(page.getByTestId("answer-result")).toHaveText("Correto");
    expect(rows().at(-1)).toMatchObject({
      question_id: id(30),
      area: "Área Fictícia Três",
      area_code: null,
      evaluation: "CORRECT",
    });
    expect(rows()).toHaveLength(5);
  });

  test("question changed between display and submission is rejected", async ({
    page,
  }) => {
    await page.goto(`${M4}/questoes/${id(45)}`);
    const file = join(CATALOG, `${id(45)}.json`);
    writeFileSync(file, readFileSync(file, "utf8") + "\n");
    await answer(page, "B");
    await expect(page.getByTestId("attempt-error")).toContainText(
      "versão divergente",
    );
    await expect(page.getByTestId("answer-result")).toHaveCount(0);
    expect(rows()).toHaveLength(5);
  });

  test("blocked question cannot be answered", async ({ page }) => {
    await page.goto(`${M4}/questoes/${id(35)}`);
    await expect(page.getByText(/Erro de proveniência/)).toBeVisible();
    await expect(page.getByRole("radio")).toHaveCount(0);
  });

  test("/questao (M2) does not record attempts", async ({ page }) => {
    await page.goto(`${M4}/questao`);
    await answer(page, "B");
    await expect(page.getByTestId("answer-result")).toHaveText("Correto");
    expect(rows()).toHaveLength(5);
  });

  test("/desempenho shows the attempts, indicators and areas", async ({
    page,
  }) => {
    await page.goto(`${M4}/desempenho`);
    await expectFinalReport(page);
  });

  test("attempts persist after restarting the application", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const before = rows();
    const restarted = await startServer(RESTART_PORT);
    try {
      await page.goto(`http://127.0.0.1:${RESTART_PORT}/desempenho`);
      await expectFinalReport(page);
    } finally {
      await stopServer(restarted);
    }
    expect(rows()).toEqual(before);
  });
});

test.describe("M4: attempts database not configured", () => {
  test("confirming shows an explicit error, no result and writes nothing", async ({
    page,
  }) => {
    const fixture = fixtureDir("m4-unconfigured");
    const ingestion = join(fixture, "data_root", "ingestion.db");
    const ingestionBefore = sha256(ingestion);
    await page.goto(`${UNCONFIGURED}/questoes/${id(7)}`);
    await expect(
      page.getByText("Enunciado sintético da questão fictícia 7"),
    ).toBeVisible();
    await answer(page, "A");
    await expect(page.getByTestId("attempt-error")).toContainText(
      "Registro de tentativas não configurado",
    );
    await expect(page.getByTestId("answer-result")).toHaveCount(0);
    await expect(page.getByText(/Gabarito oficial:/)).toHaveCount(0);
    expect(sha256(ingestion)).toBe(ingestionBefore);
    expect(existsSync(attemptsDb("m4-unconfigured"))).toBe(false);
    const sqliteFiles = readdirSync(fixture, { recursive: true }).filter(
      (name) => /\.sqlite/.test(String(name)),
    );
    expect(sqliteFiles).toEqual([]);
  });

  test("/desempenho reports that recording is not configured", async ({
    page,
  }) => {
    await page.goto(`${UNCONFIGURED}/desempenho`);
    await expect(
      page.getByText(
        "Registro de tentativas não configurado. Defina ENEM_ATTEMPTS_DB.",
      ),
    ).toHaveAttribute("role", "alert");
    await expect(page.getByTestId("indicator-total")).toHaveCount(0);
  });
});

/** Novo processo `next start` com o mesmo ambiente do servidor 3102. */
async function startServer(port: number): Promise<ChildProcess> {
  const fixture = fixtureDir("m4");
  const child = spawn("npm", ["run", "start", "--", "--port", String(port)], {
    env: {
      ...process.env,
      ENEM_M2_QUESTION_PATH: join(fixture, "question-verified.json"),
      ENEM_M2_DATA_ROOT: join(fixture, "data_root"),
      ENEM_CATALOG_DIR: CATALOG,
      ENEM_DATA_ROOT: join(fixture, "data_root"),
      ENEM_ATTEMPTS_DB: DB,
    },
    detached: true,
    stdio: "ignore",
  });
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      if (response.ok) return child;
    } catch {
      // ainda iniciando
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  await stopServer(child);
  throw new Error(`servidor na porta ${port} não iniciou`);
}

async function stopServer(child: ChildProcess): Promise<void> {
  if (child.pid === undefined || child.exitCode !== null) return;
  const exited = new Promise((resolve) => child.once("exit", resolve));
  process.kill(-child.pid, "SIGTERM");
  await exited;
}
