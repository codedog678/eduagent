import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join } from 'node:path'

const own = '/tmp/m3-task9-wholespec-7116c864-8783-4351-92c2-550bf3427d3e'
const scenario = process.env.SPEC_SCENARIO!
const historical = scenario.startsWith('history')
const validChain = scenario === 'genuine_valid'
const tag = process.env.SPEC_RUN_TAG || scenario
const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${tag}.json`), 'utf8'))

test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
  const requests: { method: string; url: string }[] = []
  const errors: string[] = []
  page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  const response = await request.get(`/ops-api/ops/policies/deployments/${fixture.id}`)
  expect(response.status()).toBe(200)
  const body = await response.json()
  await page.goto(`/ops/#/policies/${fixture.id}`)
  const detail = page.getByRole('region', { name: '策略版本详情' })
  await expect(detail.getByText(fixture.policy_hash, { exact: true }).first()).toBeVisible()
  await expect(detail.getByText(/收据是历史证据，不代表可发布资格/)).toBeVisible()
  const sourceText = await detail.locator('strong').allTextContents()
  const source = detail.getByText(historical
    ? '本部署窗口'
    : '已消费前序证据（非本部署新观测）', { exact: true }).first()
  if (historical || validChain) {
    await expect(source).toBeVisible()
    await source.scrollIntoViewIfNeeded()
    const box = await source.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
    await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
      animations: 'disabled' })
  }
  await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
    animations: 'disabled' })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  if (info.project.name === 'mobile' && scenario !== 'current') {
    const table = detail.locator('.ant-table-content').first()
    expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
    await table.hover()
    await page.mouse.wheel(1100, 0)
    await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
  }
  const hashes: Record<string, string> = {}
  for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
    const asset = await request.get(url)
    const bytes = await asset.body()
    expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
    hashes[url] = createHash('sha256').update(bytes).digest('hex')
  }
  expect(Object.keys(hashes).length).toBeGreaterThan(0)
  expect(requests.every(r => r.method === 'GET')).toBe(true)
  expect(errors).toEqual([])
  expect(overflow).toBeLessThanOrEqual(1)
  await page.screenshot({ path: `${own}/screenshots/production-${tag}-${info.project.name}.png`,
    fullPage: true, animations: 'disabled' })
  await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}.png`,
    animations: 'disabled' })
  writeFileSync(`${own}/production-${tag}-${info.project.name}.json`,
    JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes }, null, 2) + '\n')
  const health = body.gate_receipts.filter((r: { health_source: unknown }) => r.health_source)
  if (scenario === 'current') {
    expect(body.is_current).toBe(true)
    expect(body.latest_health_window.decision).toBe('hold')
    expect(health).toEqual([])
    await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
  } else if (historical) {
    expect(body.is_current).toBe(false)
    expect(health).toHaveLength(1)
    expect(health[0].receipt_id).toBe(fixture.old_receipt)
    expect(health[0].health_source.deployment_id).toBe(fixture.old)
    expect(health[0].health_source.window_id).toBe(fixture.old_window)
    const newer = await request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
    const newBody = await newer.json()
    expect(newBody.latest_health_window.decision).toBe('pass')
    expect(newBody.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
      .not.toBe(fixture.old_receipt)
  } else if (validChain) {
    expect(health).toHaveLength(2)
    expect(health.every((r: { status: string; health_source: { relation: string } }) =>
      r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  } else {
    expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
    await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  }
})
