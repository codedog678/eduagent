import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './live-e2e',
  workers: 1,
  retries: 0,
  use: { baseURL: 'http://127.0.0.1:33191', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } } },
  ],
})
