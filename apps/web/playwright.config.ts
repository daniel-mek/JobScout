import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
const root = path.resolve(__dirname, "../..");
const python = process.env.API_PYTHON || path.join(root, ".venv/bin/python");
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: {
    launchOptions: process.env.CHROMIUM_EXECUTABLE_PATH
      ? {
          executablePath: process.env.CHROMIUM_EXECUTABLE_PATH,
          args: ["--no-sandbox"],
        }
      : undefined,
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  reporter: "list",
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} scripts/test_api.py`,
      cwd: root,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: process.env.E2E_PRODUCTION
        ? "npm run start"
        : "npm run dev -- --webpack",
      url: "http://localhost:3000/login",
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
