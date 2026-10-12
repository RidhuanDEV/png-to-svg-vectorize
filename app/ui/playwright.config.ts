import { defineConfig, devices } from '@playwright/test';

// The UI is tested against the real local service (built UI + engine). Python must have the package installed
// with the [app] extra; PNGSVG_PYTHON selects the interpreter (default: "python").
const python = process.env.PNGSVG_PYTHON ?? 'python';
const PORT = 8765;

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 60_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? 'list' : 'line',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1400, height: 900 } } }],
  webServer: {
    command: `"${python}" -m pngsvg_app --port ${PORT} --token e2e --no-browser --jobs 2`,
    url: `http://127.0.0.1:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
