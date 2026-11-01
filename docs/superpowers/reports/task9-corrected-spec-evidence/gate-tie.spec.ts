import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const evidence = '/tmp/m3-task9-corrected-spec-20261102/evidence'
const status = process.env.FIX_GATE_STATUS
const fixture = JSON.parse(readFileSync(`${evidence}/live-fixture-${status}.json`, 'utf8'))

test('production PG F1: newer failed or unknown replaces older green pass', async ({ page }, info) => {
  const response = await page.request.get(`/ops-api/ops/policies/deployments/${fixture.old_deployment_id}`)
  expect(response.status()).toBe(200)
  const shown = (await response.json()).gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'formal_holdout')
  expect(shown.status).toBe(status)
  expect(shown.receipt_id).toBe('00000000-0000-0000-0000-000000000001')
  expect(fixture.authority_missing).toEqual(['formal_holdout'])
  expect(fixture.authority_accepted).toEqual([])
  await page.goto(`/ops/#/policies/${fixture.old_deployment_id}`)
  const detail = page.getByRole('region', { name: '策略版本详情' })
  const receipt = detail.locator('.ant-table-row').filter({ hasText: 'formal_holdout' })
  await expect(receipt).toHaveCount(1)
  await expect(receipt.getByText(status!, { exact: true })).toBeVisible()
  await expect(receipt.getByText('passed', { exact: true })).toHaveCount(0)
  console.log('REAL_PG_API_GATE', shown, 'ACTUAL_GATE_ROW', await receipt.innerText())
  await page.screenshot({ path: `${evidence}/screenshots/live-${status}-${info.project.name}.png`, fullPage: true })
  await detail.screenshot({ path: `${evidence}/screenshots/gate-detail-${status}-${info.project.name}.png` })
})
