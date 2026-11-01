import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const own = '/tmp/m3-task9-spec-independent'
const fixture = JSON.parse(readFileSync(`${own}/live-fixture.json`, 'utf8'))

test('Ops must display newer failed external receipt, not green older pass', async ({ page }, info) => {
  await page.goto(`/ops/#/policies/${fixture.old_deployment_id}`)
  const detail = page.getByRole('region', { name: '策略版本详情' })
  const receipt = detail.locator('.ant-table-row').filter({ hasText: 'formal_holdout' })
  await expect(receipt).toHaveCount(1)
  await page.screenshot({ path: `${own}/screenshots/gate-tie-${info.project.name}.png`, fullPage: true })
  console.log('ACTUAL_GATE_ROW', await receipt.innerText())
  await expect(receipt.getByText('failed', { exact: true })).toBeVisible()
})
