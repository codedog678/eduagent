import { expect, test } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join } from 'node:path'

const own = '/tmp/m3-task9-metrics-fix-41068737-e9a6-42a2-89f8-10d7dda22e11'
const scenario = process.env.SPEC_SCENARIO!
const historical = scenario.startsWith('history')
const validChain = scenario === 'genuine_valid' || scenario === 'leaf_active_valid'
const validLocal = scenario === 'leaf_local_valid' || scenario === 'leaf_shadow_valid'
const tag = process.env.SPEC_RUN_TAG || scenario
const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${tag}.json`), 'utf8'))

if (scenario !== 'trace_pinned') test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
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
  if (historical || validChain || validLocal) {
    const visibleSource = validLocal ? detail.getByText('本部署窗口', { exact: true }).first() : source
    await expect(visibleSource).toBeVisible()
    await visibleSource.scrollIntoViewIfNeeded()
    const box = await visibleSource.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
    await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
      animations: 'disabled' })
  }
  await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
    animations: 'disabled' })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  const scrollBefore = await detail.locator('.ant-table-content').evaluateAll(
    els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth })))
  if (info.project.name === 'mobile') {
    const table = detail.locator('.ant-table-content').first()
    expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
    await table.hover()
    await page.mouse.wheel(1100, 0)
    await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(scrollBefore[0].left)
  }
  const hashes: Record<string, string> = {}
  const assetEvidence: { url: string; bytes: number; sha256: string; status: number }[] = []
  for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
    const asset = await request.get(url)
    const bytes = await asset.body()
    expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
    hashes[url] = createHash('sha256').update(bytes).digest('hex')
    assetEvidence.push({ url, bytes: bytes.length, sha256: hashes[url], status: asset.status() })
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
    JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes,
      assetEvidence, scrollBefore,
      scrollAfter: await detail.locator('.ant-table-content').evaluateAll(
        els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth }))),
      requestContext: { detailGet: response.status(), assetGets: assetEvidence.length },
      viewport: page.viewportSize(),
    }, null, 2) + '\n')
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
  } else if (scenario.startsWith('metrics_')) {
    const valid = scenario === 'metrics_active_valid'
    expect(fixture.leaf_proof.authority_accepts).toBe(valid)
    const expected = valid ? ['canary_health', 'shadow_health']
      : scenario.startsWith('metrics_canary_') ? ['shadow_health'] : []
    expect(health.map((r: { gate_type: string }) => r.gate_type).sort(),
      'authority-rejected metric leaf must not become green Ops evidence').toEqual(expected)
  } else if (scenario.startsWith('leaf_')) {
    const gate = scenario === 'leaf_shadow_valid' ? 'shadow_health' : 'canary_health'
    const ownLeaf = health.find((r: { gate_type: string }) => r.gate_type === gate)
    expect(fixture.leaf_proof.authority_accepts).toBe(validLocal || validChain)
    if (validLocal || validChain) {
      expect(ownLeaf.receipt_id).toBe(fixture.leaf_proof.receipt_id)
      expect(ownLeaf.health_source.relation).toBe(validLocal ? 'local' : 'consumed_chain')
      expect(health).toHaveLength(scenario === 'leaf_shadow_valid' ? 1 : 2)
    } else if (scenario === 'leaf_local_bad') {
      expect(ownLeaf).toBeUndefined()
      expect(health).toHaveLength(1)
      expect(health[0].gate_type).toBe('shadow_health')
      expect(health[0].health_source.relation).toBe('consumed_chain')
    } else {
      expect(health).toEqual([])
      await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
    }
  } else if (validChain) {
    expect(health).toHaveLength(2)
    expect(health.every((r: { status: string; health_source: { relation: string } }) =>
      r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  } else {
    expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
    await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  }
})

if (scenario === 'trace_pinned') test('production actual PG Trace identity and exact dist bodies', async ({ page, request }, info) => {
  const requests: { method: string; url: string }[] = []
  const errors: string[] = []
  page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  page.on('pageerror', e => errors.push(e.message))
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  const response = await request.get(`/ops-api/ops/runs/${fixture.trace_run_id}/trace`)
  expect(response.status()).toBe(200)
  const body = await response.json()
  expect(body).toEqual(fixture.trace)
  await page.goto(`/ops/#/trace/${fixture.trace_run_id}`)
  await expect(page.getByRole('tree', { name: 'Trace 因果树' })).toBeVisible()
  await expect(page.getByText(body.effective_policy_hash, { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '运行策略绑定' })
    .getByRole('link', { name: body.deployment_id, exact: true })).toBeVisible()
  const assetEvidence: { url: string; bytes: number; sha256: string; status: number }[] = []
  for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
    const asset = await request.get(url)
    const bytes = await asset.body()
    expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
    assetEvidence.push({ url, bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex'), status: asset.status() })
  }
  expect(assetEvidence).toHaveLength(3)
  expect(requests.every(r => r.method === 'GET')).toBe(true)
  expect(errors).toEqual([])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  await page.screenshot({ path: `${own}/screenshots/trace-pinned-${info.project.name}.png`, fullPage: true })
  writeFileSync(`${own}/production-trace-${tag}-${info.project.name}.json`,
    JSON.stringify({ body, requests, assetEvidence, errors, overflow,
      detailGet: response.status(), viewport: page.viewportSize(),
      role: 'actual migrated PG engineering fixture; not release qualification' }, null, 2) + '\n')
})
