import { defineConfig, devices } from "@playwright/test";

// Explicit opt-in: connects to real, separately started production services.
// No fixtures, service replacement, automatic downloads or model installation.
export default defineConfig({
  testDir: "./e2e-real",
  timeout: 90 * 60 * 1000,
  workers: 1,
  retries: 0,
  use: { baseURL: "http://127.0.0.1:3000", trace: "off", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
