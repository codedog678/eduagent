# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: ops.spec.ts >> renders populated Ops workflows with pagination, detail, trace, and stale workers
- Location: e2e/ops.spec.ts:412:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'Runs' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: 'Runs' }) with timeout 5000ms
  - waiting for getByRole('heading', { name: 'Runs' })

```

# Test source

```ts
  317 |       return
  318 |     }
  319 |     if (path === '/expert-jobs/job-1') {
  320 |       await route.fulfill({ json: expertDetail })
  321 |       return
  322 |     }
  323 |     if (path === '/workers') {
  324 |       await route.fulfill({ json: workers })
  325 |       return
  326 |     }
  327 |     if (path.startsWith('/policies/deployments/')) {
  328 |       if (detailFailures-- > 0) {
  329 |         await route.fulfill({ status: 503, json: { detail: 'policy detail unavailable' } })
  330 |         return
  331 |       }
  332 |       const id = path.split('/').at(-1)!
  333 |       await route.fulfill({ json: policyDetail(id) })
  334 |       return
  335 |     }
  336 |     if (path.startsWith('/policies/')) {
  337 |       if (options.delayPoliciesMs && !url.searchParams.has('environment')) {
  338 |         await new Promise((resolve) => setTimeout(resolve, options.delayPoliciesMs))
  339 |         options.onSlowPolicyDone?.()
  340 |       }
  341 |       if (policyFailures-- > 0) {
  342 |         await route.fulfill({ status: 503, json: { detail: 'policy evidence unavailable' } })
  343 |         return
  344 |       }
  345 |       if (options.policyEmpty || url.searchParams.get('environment') === 'production') {
  346 |         await route.fulfill({ json: { items: [], next_cursor: null } })
  347 |         return
  348 |       }
  349 |       const second = url.searchParams.get('cursor') === 'policy-page-2'
  350 |       let items: object[] = path.endsWith('deployments')
  351 |         ? [policyDeployment(second ? secondDeploymentId : deploymentId)]
  352 |         : path.endsWith('health-windows') ? [healthWindow] : [auditEvent]
  353 |       const state = url.searchParams.get('state')
  354 |       if (state) items = [policyDeployment(state === 'frozen' ? secondDeploymentId : deploymentId)]
  355 |       if (options.malformedPolicy) items = [{ ...items[0], details: { innocent: 'must-not-render' } }]
  356 |       await route.fulfill({ json: { items, next_cursor: second || state ? null : 'policy-page-2' } })
  357 |       return
  358 |     }
  359 |     await route.fulfill({
  360 |       status: 404,
  361 |       contentType: 'application/json',
  362 |       body: JSON.stringify({ detail: `unmocked path: ${path}` }),
  363 |     })
  364 |   })
  365 | }
  366 | 
  367 | function monitorBrowser(page: Page, ignoredConsoleErrors: RegExp[] = []) {
  368 |   const errors: string[] = []
  369 |   page.on('console', (message) => {
  370 |     if (
  371 |       message.type() === 'error'
  372 |       && !ignoredConsoleErrors.some((pattern) => pattern.test(message.text()))
  373 |     ) {
  374 |       errors.push(message.text())
  375 |     }
  376 |   })
  377 |   page.on('pageerror', (error) => errors.push(error.message))
  378 |   page.on('requestfailed', (request) => {
  379 |     const message = request.failure()?.errorText || 'request failed'
  380 |     if (!message.toLowerCase().includes('aborted')) {
  381 |       errors.push(`${request.url()}: ${message}`)
  382 |     }
  383 |   })
  384 |   return errors
  385 | }
  386 | 
  387 | async function expectStableLayout(page: Page) {
  388 |   const layout = await page.evaluate(() => {
  389 |     const viewportWidth = document.documentElement.clientWidth
  390 |     const bodyOverflow = document.documentElement.scrollWidth - viewportWidth
  391 |     const header = document.querySelector('.ops-header')?.getBoundingClientRect()
  392 |     const main = document.querySelector('.ops-main')?.getBoundingClientRect()
  393 |     const clipped = Array.from(
  394 |       document.querySelectorAll<HTMLElement>(
  395 |         '.ops-nav a, .ops-page-heading h1, .ops-pagination button',
  396 |       ),
  397 |     ).filter((element) => (
  398 |       element.scrollWidth > element.clientWidth + 2
  399 |       || element.scrollHeight > element.clientHeight + 2
  400 |     )).map((element) => element.textContent?.trim() || element.className)
  401 |     return {
  402 |       bodyOverflow,
  403 |       clipped,
  404 |       coherentFlow: !header || !main || header.bottom <= main.top + 1,
  405 |     }
  406 |   })
  407 |   expect(layout.bodyOverflow).toBeLessThanOrEqual(1)
  408 |   expect(layout.clipped).toEqual([])
  409 |   expect(layout.coherentFlow).toBe(true)
  410 | }
  411 | 
  412 | test('renders populated Ops workflows with pagination, detail, trace, and stale workers', async ({ page }, testInfo) => {
  413 |   const browserErrors = monitorBrowser(page)
  414 |   await mockOps(page)
  415 | 
  416 |   await page.goto('/ops/#/runs', { waitUntil: 'commit' })
> 417 |   await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible()
      |                                                             ^ Error: expect(locator).toBeVisible() failed
  418 |   await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  419 |   await page.getByRole('button', { name: /下一页/ }).click()
  420 |   await expect(page.getByText('run-2', { exact: true })).toBeVisible()
  421 |   await page.getByRole('button', { name: /上一页/ }).click()
  422 |   await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  423 | 
  424 |   await page.getByRole('button', { name: '查看运行 run-1 详情' }).click()
  425 |   const drawer = page.getByRole('dialog', { name: '运行详情' })
  426 |   await expect(drawer).toBeVisible()
  427 |   await expect(drawer.getByText('run-worker-b', { exact: true })).toBeVisible()
  428 |   await drawer.getByRole('button', { name: '检查' }).click()
  429 |   await expect(drawer.getByText('knowledge:grammar_tenses')).toBeVisible()
  430 | 
  431 |   await drawer.getByRole('link', { name: 'a'.repeat(32) }).click()
  432 |   await expect(page.getByRole('heading', { name: '运行 Trace' })).toBeVisible()
  433 |   await expect(page.getByText('expert.wait', { exact: true })).toBeVisible()
  434 |   await expect(page.getByRole('tree')).toBeVisible()
  435 | 
  436 |   await page.getByRole('link', { name: /Workers/ }).click()
  437 |   await expect(page.getByRole('heading', { name: 'Workers' })).toBeVisible()
  438 |   await expect(page.getByText('expert-worker-stale', { exact: true })).toBeVisible()
  439 |   await expect(page.getByText('stale', { exact: true }).first()).toBeVisible()
  440 | 
  441 |   await expect(page.getByRole('button', { name: /取消|重试任务|重新入队/ })).toHaveCount(0)
  442 |   await expectStableLayout(page)
  443 |   if (process.env.OPS_SCREENSHOT_DIR) {
  444 |     await page.screenshot({
  445 |       path: `${process.env.OPS_SCREENSHOT_DIR}/ops-${testInfo.project.name}.png`,
  446 |       fullPage: true,
  447 |     })
  448 |   }
  449 |   expect(browserErrors).toEqual([])
  450 | })
  451 | 
  452 | test('shows loading and empty states without layout shift', async ({ page }) => {
  453 |   const browserErrors = monitorBrowser(page)
  454 |   await mockOps(page, { runPages: 'empty' })
  455 | 
  456 |   await page.goto('/ops/#/runs', { waitUntil: 'commit' })
  457 |   await expect(page.locator('.ant-skeleton')).toBeVisible()
  458 |   await expect(page.getByText('没有符合条件的运行')).toBeVisible()
  459 |   await expectStableLayout(page)
  460 |   expect(browserErrors).toEqual([])
  461 | })
  462 | 
  463 | test('shows retryable API errors and recovers', async ({ page }) => {
  464 |   const browserErrors = monitorBrowser(
  465 |     page,
  466 |     [/Failed to load resource:.*500 \(Internal Server Error\)/],
  467 |   )
  468 |   await mockOps(page, { runFailureCount: 2 })
  469 | 
  470 |   await page.goto('/ops/#/runs')
  471 |   await expect(page.getByText('Runs 加载失败')).toBeVisible()
  472 |   await expect(page.getByText('temporary database failure')).toBeVisible()
  473 |   await page.getByRole('button', { name: /重\s*试/ }).click()
  474 |   await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  475 |   await expectStableLayout(page)
  476 |   expect(browserErrors).toEqual([])
  477 | })
  478 | 
  479 | test('keeps bearer token in session storage and retries authorization', async ({ page }) => {
  480 |   const browserErrors = monitorBrowser(
  481 |     page,
  482 |     [/Failed to load resource:.*401 \(Unauthorized\)/],
  483 |   )
  484 |   await mockOps(page, { requireToken: true })
  485 | 
  486 |   await page.goto('/ops/#/runs')
  487 |   await expect(page.getByRole('heading', { name: '需要 Ops 访问凭证' })).toBeVisible()
  488 |   await page.getByLabel('OPS API Token').fill('browser-test-token')
  489 |   await page.getByRole('button', { name: '验证并重试' }).click()
  490 |   await expect(page.getByText('run-1', { exact: true })).toBeVisible()
  491 |   expect(
  492 |     await page.evaluate(() => sessionStorage.getItem('eduagent.ops.token')),
  493 |   ).toBe('browser-test-token')
  494 |   await expectStableLayout(page)
  495 |   expect(browserErrors).toEqual([])
  496 | })
  497 | 
  498 | test('policy evidence filters, cursor pages, detail, metrics and audit are read only', async ({ page }, testInfo) => {
  499 |   const errors = monitorBrowser(page)
  500 |   const requests: Array<{ method: string; url: string }> = []
  501 |   page.on('request', (request) => {
  502 |     if (request.url().includes('/ops-api/')) requests.push({ method: request.method(), url: request.url() })
  503 |   })
  504 |   await mockOps(page)
  505 |   await page.goto('/ops/#/policies')
  506 |   await expect(page.getByRole('heading', { name: 'Policies', exact: true })).toBeVisible()
  507 |   await expect(page.getByText(deploymentId, { exact: true })).toBeVisible()
  508 |   if (testInfo.project.name === 'mobile') {
  509 |     const overflowTable = page.locator('.ant-table-content').first()
  510 |     expect(await overflowTable.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
  511 |     await overflowTable.hover()
  512 |     await page.mouse.wheel(900, 0)
  513 |     await expect.poll(() => overflowTable.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0)
  514 |     await page.mouse.wheel(-900, 0)
  515 |   }
  516 |   await page.getByRole('button', { name: /下一页/ }).click()
  517 |   await expect(page.getByText(secondDeploymentId, { exact: true })).toBeVisible()
```