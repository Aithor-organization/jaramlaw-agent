import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4321",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:4321/api/health",
    reuseExistingServer: true,
    timeout: 120_000,
    env: {
      PORT: "4321",
      JARAMLAW_DISABLE_PYTHON_BRIDGE: "1",
    },
  },
});
