import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
const own = '/tmp/m3-task9-code-20261102-5TNycP'
const sha = (data: Buffer) => createHash('sha256').update(data).digest('hex')

test('real production HTTP assets and GET-only current health detail', async ({ page }, info) => {
  const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))
  const errors: string[] = []
  const methods: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (r.url().includes('/ops-api/')) methods.push(r.method()) })
  const html = await page.request.get('/ops/')
  const bytes = await html.body()
  expect(bytes.equals(readFileSync(`${own}/frontend/dist/ops/index.html`))).toBeTruthy()
  const assets = [...bytes.toString().matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map(x => x[1])
  const hashes: Record<string, string> = { 'ops/index.html': sha(bytes) }
  for (const asset of assets) {
    const response = await page.request.get(asset)
    const data = await response.body()
    expect(data.equals(readFileSync(`${own}/frontend/dist${asset}`))).toBeTruthy()
    hashes[asset] = sha(data)
  }
  await page.goto(`/ops/#/policies/${fixture.current}`)
  const section = page.locator('section[aria-label="策略版本详情"]')
  await expect(section.locator('.ant-descriptions')).toBeVisible()
  await expect(section.getByText('canary_health', { exact: true })).toBeVisible()
  await expect(section.locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })).toBeVisible()
  await expect(section.locator('.ant-tag').filter({ hasText: /^\s*hold\s*$/ })).toBeVisible()
  const response = await page.request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  const api = await response.json()
  expect(api.is_current).toBeTruthy()
  expect(api.latest_health_window.decision).toBe('hold')
  expect(api.gate_receipts[0].receipt_id).toBe(fixture.old_receipt_id)
  expect(fixture.receipt_deployment).not.toBe(fixture.current)
  const width = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(width).toBeLessThanOrEqual(1)
  const table = section.locator('.ant-table-content').first()
  if (info.project.name === 'mobile') {
    expect(await table.evaluate(e => e.scrollWidth > e.clientWidth)).toBeTruthy()
    await table.hover()
    await page.mouse.wheel(800, 0)
    await expect.poll(() => table.evaluate(e => e.scrollLeft)).toBeGreaterThan(0)
    await page.mouse.wheel(-800, 0)
  }
  await section.screenshot({ path: `${own}/screenshots/live2-cross-binding-${info.project.name}.png` })
  await page.screenshot({ path: `${own}/screenshots/live2-policies-${info.project.name}.png`, fullPage: true })
  expect(errors).toEqual([])
  expect([...new Set(methods)]).toEqual(['GET'])
  expect(await page.getByRole('button', { name: /发布|回滚|冻结|取消|重新入队/ }).count()).toBe(0)
  writeFileSync(`${own}/production-${info.project.name}.json`, JSON.stringify({
    role: 'fresh browser observation of a defect, not a correctness PASS',
    hashes, methods, errors, bodyOverflow: width,
    current: fixture.current, actual_receipt: fixture.old_receipt_id, source_deployment: fixture.receipt_deployment,
  }, null, 2))
})

test('current detail must not label foreign health receipt passed', async ({ page }, info) => {
  const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))
  await page.goto(`/ops/#/policies/${fixture.current}`)
  const section = page.locator('section[aria-label="策略版本详情"]')
  await expect(section.locator('.ant-descriptions')).toBeVisible()
  await section.screenshot({ path: `${own}/screenshots/live2-correctness-${info.project.name}.png` })
  await expect(section.locator('.ant-tag').filter({ hasText: /^\s*passed\s*$/ })).toHaveCount(0)
})
