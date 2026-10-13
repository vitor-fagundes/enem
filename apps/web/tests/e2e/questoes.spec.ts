import { expect, type Page, test } from "@playwright/test";

// Catálogo sintético gerado por tests/e2e/support/build_m2_fixture.py.
// 3100: catalog/ (questões fictícias 7, 12 e 30 + entradas rejeitadas).
// 3101: catalog-compromised/ (12 com gabarito adulterado; 30 com caderno adulterado).
const COMPROMISED_SERVER = "http://127.0.0.1:3101";
const id = (n: number) => `enem-1999-d9-cd9-q${n}`;
const KEYS = { 7: "A", 12: "C", 30: "E" } as const;

const entries = (page: Page) => page.getByTestId("catalog-entry");
const confirm = (page: Page) => page.getByRole("button", { name: "Confirmar" });
const nav = (page: Page) =>
  page.getByRole("navigation", { name: "Navegação entre questões" });

async function answer(page: Page, label: string) {
  await page.getByRole("radio", { name: new RegExp(`^${label} `) }).check();
  await confirm(page).click();
}

test("home links to the catalog and keeps the M2 link", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Responder a questão do M2" }),
  ).toHaveAttribute("href", "/questao");
  await page.getByRole("link", { name: "Catálogo de questões (M3)" }).click();
  await expect(page).toHaveURL(/\/questoes$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Questões");
});

test("catalog lists valid questions in numeric order with area and source state", async ({
  page,
}) => {
  await page.goto("/questoes");
  await expect(entries(page)).toHaveCount(3);
  const expected = [
    [7, "Área Fictícia Um"],
    [12, "Área Fictícia Dois"],
    [30, "Área Fictícia Três"],
  ] as const;
  for (const [i, [number, area]] of expected.entries()) {
    const entry = entries(page).nth(i);
    await expect(
      entry.getByRole("link", { name: `Questão ${number}`, exact: true }),
    ).toHaveAttribute("href", `/questoes/${id(number)}`);
    await expect(entry).toContainText(area);
    await expect(entry).toContainText("Fonte verificada");
    await expect(entry).not.toContainText("gabarito não verificado");
  }
});

test("catalog warns about rejected files and ignores backups and non-JSON", async ({
  page,
}) => {
  await page.goto("/questoes");
  const warnings = page.getByTestId("catalog-warning");
  const expected: Array<[string, RegExp]> = [
    ["copia-da-50.json", /posição duplicada \(enem-1999-d9-cd9-q50\)/],
    [`${id(3)}.json`, /somente COMMON/],
    [`${id(40)}.json`, /sem confirmação humana registrada/],
    [`${id(50)}.json`, /posição duplicada \(enem-1999-d9-cd9-q50\)/],
    [`${id(60)}.json`, /alternatives deve ter exatamente A–E/],
    [
      "nome-diferente.json",
      /nome do arquivo deve ser enem-1999-d9-cd9-q41\.json/,
    ],
    ["quebrado.json", /JSON malformado/],
  ];
  await expect(warnings).toHaveCount(expected.length);
  for (const [i, [fileName, reason]] of expected.entries()) {
    await expect(warnings.nth(i)).toContainText(fileName);
    await expect(warnings.nth(i)).toContainText(reason);
  }
  const section = page.getByRole("region", {
    name: "Arquivos fora do catálogo",
  });
  await expect(section).not.toContainText(".bak-");
  await expect(section).not.toContainText("notas.txt");
  await expect(section).not.toContainText("subdiretorio");
});

test("opens a question from the catalog and answers it correctly", async ({
  page,
}) => {
  await page.goto("/questoes");
  await page.getByRole("link", { name: "Questão 12", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/questoes/${id(12)}$`));
  await expect(
    page.getByText("Enunciado sintético da questão fictícia 12"),
  ).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(5);
  await expect(confirm(page)).toBeDisabled();
  await answer(page, KEYS[12]);
  await expect(page.getByTestId("answer-result")).toHaveText("Correto");
  await expect(page.getByText(`Gabarito oficial: ${KEYS[12]}`)).toBeVisible();
  const source = page.getByRole("region", { name: "Fonte" });
  await expect(source).toContainText("questão 12");
  await expect(source).toContainText("índice zero-based 2 (página 3 do PDF)");
  await expect(source).toContainText(
    "Transcrição assistida por LLM, conferida visualmente e confirmada pessoalmente pelo usuário.",
  );
});

test("incorrect answer shows Incorreto and the official key", async ({
  page,
}) => {
  await page.goto(`/questoes/${id(30)}`);
  await answer(page, "B");
  await expect(page.getByTestId("answer-result")).toHaveText("Incorreto");
  await expect(page.getByText(`Gabarito oficial: ${KEYS[30]}`)).toBeVisible();
});

test("previous/next follow catalog order with no links at the edges", async ({
  page,
}) => {
  await page.goto(`/questoes/${id(7)}`);
  await expect(nav(page).getByRole("link", { name: /Anterior/ })).toHaveCount(
    0,
  );
  await nav(page).getByRole("link", { name: "Próxima: questão 12" }).click();
  await expect(page).toHaveURL(new RegExp(`/questoes/${id(12)}$`));
  await nav(page).getByRole("link", { name: "Próxima: questão 30" }).click();
  await expect(page).toHaveURL(new RegExp(`/questoes/${id(30)}$`));
  await expect(nav(page).getByRole("link", { name: /Próxima/ })).toHaveCount(0);
  await nav(page).getByRole("link", { name: "Anterior: questão 12" }).click();
  await expect(page).toHaveURL(new RegExp(`/questoes/${id(12)}$`));
  await nav(page).getByRole("link", { name: "Anterior: questão 7" }).click();
  await expect(page).toHaveURL(new RegExp(`/questoes/${id(7)}$`));
});

test("navigating between questions clears the answer", async ({ page }) => {
  await page.goto(`/questoes/${id(7)}`);
  await answer(page, KEYS[7]);
  await expect(page.getByTestId("answer-result")).toHaveText("Correto");
  await nav(page).getByRole("link", { name: "Próxima: questão 12" }).click();
  await expect(
    page.getByText("Enunciado sintético da questão fictícia 12"),
  ).toBeVisible();
  await expect(page.getByTestId("answer-result")).toHaveCount(0);
  for (const radio of await page.getByRole("radio").all()) {
    await expect(radio).not.toBeChecked();
  }
  await expect(confirm(page)).toBeDisabled();
  await nav(page).getByRole("link", { name: "Anterior: questão 7" }).click();
  await expect(
    page.getByText("Enunciado sintético da questão fictícia 7"),
  ).toBeVisible();
  await expect(page.getByTestId("answer-result")).toHaveCount(0);
  await expect(confirm(page)).toBeDisabled();
});

test("unknown or excluded IDs respond 404", async ({ page }) => {
  for (const path of [
    "/questoes/inexistente",
    `/questoes/${id(40)}`,
    `/questoes/${id(41)}`,
    `/questoes/${id(50)}`,
    `/questoes/${id(99)}`,
  ]) {
    const response = await page.goto(path);
    expect(response?.status(), path).toBe(404);
  }
});

test("compromised answer key shows the question without correction", async ({
  page,
}) => {
  await page.goto(`${COMPROMISED_SERVER}/questoes/${id(12)}`);
  await expect(
    page.getByText(/gabarito não verificado/i).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Enunciado sintético da questão fictícia 12"),
  ).toBeVisible();
  await answer(page, KEYS[12]);
  await expect(page.getByTestId("answer-result")).not.toHaveText(
    /Correto|Incorreto/,
  );
  await expect(page.getByText(/Gabarito oficial:/)).toHaveCount(0);
});

test("compromised booklet blocks only the affected question", async ({
  page,
}) => {
  await page.goto(`${COMPROMISED_SERVER}/questoes`);
  await expect(entries(page)).toHaveCount(3);
  await expect(entries(page).nth(0)).toContainText("Fonte verificada");
  await expect(entries(page).nth(0).getByRole("link")).toHaveCount(1);
  await expect(entries(page).nth(1)).toContainText(
    "Fonte verificada; gabarito não verificado",
  );
  await expect(entries(page).nth(1).getByRole("link")).toHaveCount(1);
  await expect(entries(page).nth(2)).toContainText(
    "Erro de proveniência: questão indisponível",
  );
  await expect(entries(page).nth(2).getByRole("link")).toHaveCount(0);

  await page.goto(`${COMPROMISED_SERVER}/questoes/${id(30)}`);
  await expect(page.getByText(/Erro de proveniência/)).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await expect(
    page.getByText("Enunciado sintético da questão fictícia 30"),
  ).toHaveCount(0);

  // A navegação pula a questão bloqueada.
  await page.goto(`${COMPROMISED_SERVER}/questoes/${id(12)}`);
  await expect(nav(page).getByRole("link", { name: /Próxima/ })).toHaveCount(0);
  await page.goto(`${COMPROMISED_SERVER}/questoes/${id(7)}`);
  await answer(page, KEYS[7]);
  await expect(page.getByTestId("answer-result")).toHaveText("Correto");
});
