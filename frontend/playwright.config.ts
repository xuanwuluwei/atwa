import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:8743',
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'ATWA_ENV=test python -m alembic upgrade head && ATWA_ENV=test python -m uvicorn server.main:app --port 8743 --log-level warning',
    port: 8743,
    reuseExistingServer: !process.env.CI,
    timeout: 15000,
    cwd: '..',
  },
});
