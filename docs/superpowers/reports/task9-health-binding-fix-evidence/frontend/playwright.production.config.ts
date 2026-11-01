import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './live-e2e', workers: 1, retries: 0, forbidOnly: true,
  reporter: [['line'], ['junit']],
  use: { baseURL: 'http://127.0.0.1:33521', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
})
