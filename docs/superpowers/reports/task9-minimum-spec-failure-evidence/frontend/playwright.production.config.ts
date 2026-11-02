import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './live-e2e', workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:38731', trace: 'on' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
})
