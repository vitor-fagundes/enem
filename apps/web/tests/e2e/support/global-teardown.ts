import { rmSync } from "node:fs";
import { RUN_DIR_PREFIX } from "./run-dir";

/** Remove o diretório temporário criado para esta execução do e2e. */
export default function globalTeardown() {
  const dir = process.env.ENEM_E2E_RUN_DIR;
  if (dir?.startsWith(RUN_DIR_PREFIX)) {
    rmSync(dir, { recursive: true, force: true });
  }
}
