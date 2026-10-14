/**
 * Mapeamento da área curada (texto livre) para o código canônico da SPEC-001
 * FR-017 (docs/m4-registro-tentativas.md, Decisões > Áreas). Igualdade exata
 * após `trim` e normalização Unicode NFC; sem correspondência aproximada.
 * `RED` não se aplica a questões objetivas. Função pura, sem I/O.
 */

export const AREA_CODES = ["LC", "CH", "CN", "MT"] as const;
export type AreaCode = (typeof AREA_CODES)[number];

export const AREA_NAMES: Record<AreaCode, string> = {
  LC: "Linguagens, Códigos e suas Tecnologias",
  CH: "Ciências Humanas e suas Tecnologias",
  CN: "Ciências da Natureza e suas Tecnologias",
  MT: "Matemática e suas Tecnologias",
};

const BY_NAME = new Map<string, AreaCode>(
  AREA_CODES.map((code) => [AREA_NAMES[code].normalize("NFC"), code]),
);

/** Código canônico da área ou `null` quando o texto não é reconhecido. */
export function mapAreaCode(area: string): AreaCode | null {
  return BY_NAME.get(area.trim().normalize("NFC")) ?? null;
}
