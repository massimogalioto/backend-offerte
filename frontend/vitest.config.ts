import { defineConfig } from "vitest/config";
export default defineConfig({ test: { include: ["cte-batch.test.ts", "lib/**/*.test.ts"] } });
