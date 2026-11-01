import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const own = '/tmp/m3-task9-corrected-spec-20261102'
const evidence = `${own}/evidence`
const fixture = JSON.parse(readFileSync(`${evidence}/live-fixture-${process.env.FIX_GATE_STATUS}.json`, 'utf8'))

test('fresh production HTTP bytes and immutable old/new Run table drawer Trace links', async ({ page }, info) => {
  const methods: string[] = []
  page.on('request', req => { if (req.url().includes('/ops-api/')) methods.push(req.method()) })
  const hashes: Record<string, string> = {}
  for (const rel of ['ops/index.html', ...readdirSync(`${own}/frontend/dist/assets`).map(x => `assets/${x}`)]) {
    const url = rel === 'ops/index.html' ? '/ops/' : `/${rel}`
    const response = await page.request.get(url)
    expect(response.status()).toBe(200)
    const actual = await response.body()
    expect(actual.equals(readFileSync(`${own}/frontend/dist/${rel}`))).toBe(true)
    hashes[rel] = createHash('sha256').update(actual).digest('hex')
  }
  await page.goto('/ops/#/runs')
  const oldRow = page.locator('.ant-table-row').filter({ hasText: fixture.old_run_id })
  const newRow = page.locator('.ant-table-row').filter({ hasText: fixture.new_run_id })
  await expect(oldRow).toHaveCount(1)
  await expect(newRow).toHaveCount(1)
  await expect(oldRow.getByText(fixture.old_policy_hash, { exact: true })).toBeVisible()
  await expect(newRow.getByText(fixture.new_policy_hash, { exact: true })).toBeVisible()
  await expect(oldRow.getByText('candidate · rehearsal', { exact: true })).toBeVisible()
  await expect(newRow.getByText('stable · rehearsal', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: `查看运行 ${fixture.old_run_id} 详情` }).click()
  const drawer = page.getByRole('dialog', { name: '运行详情' })
  await expect(drawer.getByText(fixture.old_policy_hash, { exact: true })).toBeVisible()
  await expect(drawer.getByText('candidate', { exact: true })).toBeVisible()
  await expect(drawer.getByText('rehearsal', { exact: true })).toBeVisible()
  await page.screenshot({ path: `${evidence}/screenshots/fresh-run-${info.project.name}.png`, fullPage: true })
  await drawer.getByRole('link', { name: fixture.old_deployment_id, exact: true }).click()
  const detail = page.getByRole('region', { name: '策略版本详情' })
  await expect(detail.getByText(fixture.old_policy_hash, { exact: true })).toBeVisible()
  await expect(detail.getByText('当前版本 3', { exact: false })).toBeVisible()
  await expect(page.locator('.ant-card')).toHaveCount(0)
  await page.getByRole('link', { name: 'Runs', exact: true }).click()
  await page.getByRole('button', { name: `查看运行 ${fixture.new_run_id} 详情` }).click()
  await expect(drawer.getByText(fixture.new_policy_hash, { exact: true })).toBeVisible()
  await expect(drawer.getByText('stable', { exact: true })).toBeVisible()
  await expect(drawer.getByRole('link', { name: fixture.current_deployment_id, exact: true })).toBeVisible()
  const traceResponse = await page.request.get(`/ops-api/ops/runs/${fixture.old_run_id}/trace`)
  expect(traceResponse.status()).toBe(200)
  const trace = await traceResponse.json()
  await drawer.getByRole('link', { name: (await (await page.request.get(`/ops-api/ops/runs/${fixture.new_run_id}`)).json()).trace_id, exact: true }).click()
  await expect(page.getByRole('region', { name: '运行策略绑定' }).getByText('stable · rehearsal')).toBeVisible()
  expect(trace.effective_policy_hash).toBe(fixture.old_policy_hash)
  expect(trace.deployment_id).toBe(fixture.old_deployment_id)
  expect(Object.keys(trace)).not.toContain('state_namespace')
  expect(methods.length).toBeGreaterThan(4)
  expect(methods.every(method => method === 'GET')).toBe(true)
  writeFileSync(`${evidence}/production-http-${info.project.name}.json`, JSON.stringify({ hashes, methods, trace_binding: {
    effective_policy_hash: trace.effective_policy_hash, deployment_id: trace.deployment_id,
    policy_cohort: trace.policy_cohort, namespace_class: trace.namespace_class,
  } }, null, 2) + '\n')
})
