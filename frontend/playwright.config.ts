import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    { command: "env -u PYTHONPATH ../.venv/bin/python -m uvicorn ui_fixture_server:app --app-dir ../tests --host 127.0.0.1 --port 8001", url: "http://127.0.0.1:8001/api/v1/health", timeout: 30000, reuseExistingServer: false },
    { command: "npm run start -- --port 3100", env: { VIDEOMIND_API_URL: "http://127.0.0.1:8001", NEXT_TELEMETRY_DISABLED: "1" }, url: "http://127.0.0.1:3100", timeout: 30000, reuseExistingServer: false },
  ],
});
