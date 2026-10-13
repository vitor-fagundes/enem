import { createHash } from "node:crypto";
import { expect, type Page, test } from "@playwright/test";

// Fixture sintética gerada por tests/e2e/support/build_m2_fixture.py.
const BOOKLET_SHA = createHash("sha256")
  .update("%PDF-sintetico caderno ficticio enem-rei m2\n")
  .digest("hex");
const BOOKLET_URL = "https://example.invalid/sintetico/caderno-ficticio.pdf";
const UNVERIFIED_KEY_SERVER = "http://127.0.0.1:3101";

const radios = (page: Page) => page.getByRole("radio");
const confirm = (page: Page) => page.getByRole("button", { name: "Confirmar" });

test("shows the statement and exactly five labelled alternatives", async ({
  page,
}) => {
  await page.goto("/questao");
  await expect(
    page.getByText("Enunciado sintético de teste: escolha a opção certa"),
  ).toBeVisible();
  await expect(radios(page)).toHaveCount(5);
  for (const label of ["A", "B", "C", "D", "E"]) {
    await expect(
      page.getByRole("radio", {
        name: `${label} opção fictícia ${label.toLowerCase()}`,
      }),
    ).toBeVisible();
  }
  await expect(page.getByText(/erro de proveniência/i)).toHaveCount(0);
  await expect(page.getByText(/gabarito não verificado/i)).toHaveCount(0);
});

test("confirm is disabled until an alternative is selected", async ({
  page,
}) => {
  await page.goto("/questao");
  await expect(confirm(page)).toBeDisabled();
  await radios(page).nth(3).check();
  await expect(confirm(page)).toBeEnabled();
});

test("correct answer shows Correto and the official key", async ({ page }) => {
  await page.goto("/questao");
  await page.getByRole("radio", { name: /^B / }).check();
  await confirm(page).click();
  await expect(page.getByTestId("answer-result")).toHaveText("Correto");
  await expect(page.getByText("Gabarito oficial: B")).toBeVisible();
});

test("incorrect answer shows Incorreto and the official key", async ({
  page,
}) => {
  await page.goto("/questao");
  await page.getByRole("radio", { name: /^D / }).check();
  await confirm(page).click();
  await expect(page.getByTestId("answer-result")).toHaveText("Incorreto");
  await expect(page.getByText("Gabarito oficial: B")).toBeVisible();
});

test("unverified answer key shows the warning and no correction", async ({
  page,
}) => {
  await page.goto(`${UNVERIFIED_KEY_SERVER}/questao`);
  await expect(
    page.getByText(/gabarito não verificado/i).first(),
  ).toBeVisible();
  await expect(radios(page)).toHaveCount(5);
  await page.getByRole("radio", { name: /^B / }).check();
  await confirm(page).click();
  await expect(page.getByTestId("answer-result")).not.toHaveText(
    /Correto|Incorreto/,
  );
  await expect(page.getByText(/Gabarito oficial:/)).toHaveCount(0);
});

test("source block shows URL, SHA-256, physical page and verification label", async ({
  page,
}) => {
  await page.goto("/questao");
  const source = page.getByRole("region", { name: "Fonte" });
  await expect(source.getByRole("link", { name: BOOKLET_URL })).toBeVisible();
  await expect(source.getByText(BOOKLET_SHA)).toBeVisible();
  await expect(
    source.getByText("índice zero-based 2 (página 3 do PDF)"),
  ).toBeVisible();
  await expect(
    source.getByText(
      "Transcrição assistida por LLM, conferida visualmente e confirmada pessoalmente pelo usuário.",
    ),
  ).toBeVisible();
  await expect(source.getByText(/Conferência: fixture\./)).toBeVisible();
  await expect(
    source.getByText(/Horário da conferência: não registrado\./),
  ).toBeVisible();
  await expect(
    source.getByText(/Confirmação registrada em: 2000-01-02T00:00:00Z\./),
  ).toBeVisible();
});

test("source block without recorded confirmation keeps the unverified label", async ({
  page,
}) => {
  await page.goto(`${UNVERIFIED_KEY_SERVER}/questao`);
  const source = page.getByRole("region", { name: "Fonte" });
  await expect(
    source.getByText(
      "Transcrição assistida por LLM, conferida por comparação visual (não verificada pessoalmente pelo usuário).",
    ),
  ).toBeVisible();
  await expect(source.getByText(/Confirmação registrada em/)).toHaveCount(0);
});

test("reloading does not preserve the answer", async ({ page }) => {
  await page.goto("/questao");
  await page.getByRole("radio", { name: /^C / }).check();
  await confirm(page).click();
  await expect(page.getByTestId("answer-result")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("answer-result")).toHaveCount(0);
  for (const radio of await radios(page).all()) {
    await expect(radio).not.toBeChecked();
  }
  await expect(confirm(page)).toBeDisabled();
});
