import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join } from 'node:path'

const own = '/tmp/m3-task9-health-fix-20261102-xtfx61'
const fixture = JSON.parse(readFileSync(process.env.LIVE_FIXTURE || join(own, 'live-fixture.json'), 'utf8'))

for (const name of ['current', 'history'] as const) {
  test(`real PG production ${name} binds health evidence to the exact deployment`, async ({ page, request }, info) => {
    const scenario = fixture.scenarios[name]
    const id = name === 'current' ? scenario.current : scenario.old
    const requests: Array<{ method: string; url: string }> = []
    const errors: string[] = []
    page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
    page.on('pageerror', e => errors.push(e.message))
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
    const response = await request.get(`/ops-api/ops/policies/deployments/${id}`)
    expect(response.status()).toBe(200)
    const body = await response.json()
    const shown = body.gate_receipts.filter((r: { gate_type: string }) => r.gate_type === 'canary_health')
    if (name === 'current') {
      expect(body.is_current).toBe(true)
      expect(body.latest_health_window.decision).toBe('hold')
      expect(shown).toEqual([])
    } else {
      expect(body.is_current).toBe(false)
      expect(shown).toHaveLength(1)
      expect(shown[0].receipt_id).toBe(scenario.old_receipt_id)
      expect(shown[0].health_source).toMatchObject({
        relation: 'local', deployment_id: scenario.old, window_id: scenario.old_window,
      })
      const newer = await request.get(`/ops-api/ops/policies/deployments/${scenario.current}`)
      const current = await newer.json()
      expect(current.is_current).toBe(true)
      expect(current.latest_health_window.decision).toBe('pass')
      expect(current.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
        .not.toBe(scenario.old_receipt_id)
    }
    await page.goto(`/ops/#/policies/${id}`)
    const detail = page.getByRole('region', { name: '策略版本详情' })
    await expect(detail.getByText('b'.repeat(64), { exact: true })).toHaveCount(0)
    await expect(detail.getByText(scenario.policy_hash, { exact: true }).first()).toBeVisible()
    if (name === 'current') {
      await expect(detail.getByText('hold', { exact: true })).toBeVisible()
      await expect(detail.getByText('暂无 Gate 收据')).toBeVisible()
      await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
    } else {
      await expect(detail.getByText('passed', { exact: true }).first()).toBeVisible()
      await expect(detail.getByText(`Window ${scenario.old_window}`, { exact: true })).toBeVisible()
      await expect(detail.getByText('本部署窗口', { exact: true })).toBeVisible()
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(1)
    if (info.project.name === 'mobile' && name === 'history') {
      const table = detail.locator('.ant-table-content').first()
      expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
      await table.hover()
      await page.mouse.wheel(1500, 0)
      await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
    }
    const assetHashes: Record<string, string> = {}
    for (const url of [...new Set(requests.map(r => r.url).filter(url => /\/assets\/.*\.(js|css)$/.test(url)))]) {
      const asset = await request.get(url)
      expect(asset.status()).toBe(200)
      const received = await asset.body()
      const local = readFileSync(join(own, 'frontend/dist', new URL(url).pathname))
      expect(received.equals(local)).toBe(true)
      assetHashes[url] = createHash('sha256').update(received).digest('hex')
    }
    expect(Object.keys(assetHashes).length).toBeGreaterThan(0)
    expect(requests.every(r => r.method === 'GET')).toBe(true)
    expect(errors).toEqual([])
    await page.screenshot({ path: `${own}/screenshots/production-${name}-${info.project.name}.png`,
      fullPage: true, animations: 'disabled' })
    writeFileSync(`${own}/production-${name}-${info.project.name}.json`,
      JSON.stringify({ role: fixture.role, body, requests, assetHashes, errors, overflow }, null, 2) + '\n')
  })
}
