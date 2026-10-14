import { describe, expect, test } from "vitest";
import { AREA_NAMES, mapAreaCode } from "../../src/domain/area";

describe("mapAreaCode", () => {
  test("maps the four official area names", () => {
    expect(mapAreaCode("Linguagens, Códigos e suas Tecnologias")).toBe("LC");
    expect(mapAreaCode("Ciências Humanas e suas Tecnologias")).toBe("CH");
    expect(mapAreaCode("Ciências da Natureza e suas Tecnologias")).toBe("CN");
    expect(mapAreaCode("Matemática e suas Tecnologias")).toBe("MT");
  });

  test("ignores leading and trailing whitespace", () => {
    expect(mapAreaCode("  Matemática e suas Tecnologias\n")).toBe("MT");
  });

  test("normalizes Unicode to NFC before comparing", () => {
    const decomposed = AREA_NAMES.CH.normalize("NFD");
    expect(decomposed).not.toBe(AREA_NAMES.CH);
    expect(mapAreaCode(decomposed)).toBe("CH");
  });

  test("unrecognized text stays unmapped (no approximate matching)", () => {
    for (const text of [
      "Área Fictícia Um",
      "matemática e suas tecnologias",
      "Matemática",
      "Matemática  e suas Tecnologias",
      "Redação",
      "",
    ]) {
      expect(mapAreaCode(text), text).toBeNull();
    }
  });
});
