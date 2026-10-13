import setup from '../fixtures/corporate_purchase_remediation_setup.mjs';
import verify from '../fixtures/corporate_purchase_remediation_verify.mjs';
import { mkdirSync } from 'node:fs';
import assert from 'node:assert/strict';

const { chromium } = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({headless: true, ...(process.env.ADMINRETRO_CHROME_PATH
  ? {executablePath: process.env.ADMINRETRO_CHROME_PATH} : {})});
const baseUrl = process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin';
mkdirSync('output/playwright', {recursive: true});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.setDefaultTimeout(10000);
  await page.goto(baseUrl + '/login');
  await setup(page);
  await page.goto(baseUrl + '/purchases');
  await verify(page);
  await page.close();

  // Both tabs enqueue different quantities while the same Web Lock is held.
  const context = await browser.newContext();
  const tabs = await Promise.all([context.newPage(), context.newPage()]);
  for (const tab of tabs) {
    tab.setDefaultTimeout(10000);
    await tab.goto(baseUrl + '/login');
    await setup(tab, {seedStorage: tab === tabs[0]});
    await tab.goto(baseUrl + '/purchases');
    await tab.getByText('REM-UI-001', {exact: true}).first().click();
  }
  console.log('Concurrent tabs initialized');
  await tabs[0].getByRole('textbox', {name: 'Cantidad a recibir'}).first().fill('0.5');
  await tabs[1].getByRole('textbox', {name: 'Cantidad a recibir'}).first().fill('0.75');
  assert.equal(await tabs[0].getByRole('textbox', {name: 'Cantidad a recibir'}).first().inputValue(), '0.5');
  assert.equal(await tabs[1].getByRole('textbox', {name: 'Cantidad a recibir'}).first().inputValue(), '0.75');
  await tabs[0].evaluate(() => {
    window.__corporateQaLockAcquired = false;
    void navigator.locks.request('corporate-intent:v1:org-qa:actor-qa', async () => {
      window.__corporateQaLockAcquired = true;
      await new Promise(release => { window.__releaseCorporateQaLock = release; });
    });
  });
  await tabs[0].waitForFunction(() => window.__corporateQaLockAcquired, null, {timeout: 10000});
  console.log('Concurrent lock acquired');
  for (const tab of tabs) tab.once('dialog', dialog => dialog.accept());
  await Promise.all(tabs.map(tab => tab.getByRole('button', {name: 'Recibir', exact: true}).first().click()));
  console.log('Both intents queued');
  assert.deepEqual(await Promise.all(tabs.map(tab => tab.evaluate(async () =>
    (await window.__corporateQaEvidenceV2()).requests.length))), [0, 0]);
  await tabs[0].evaluate(() => window.__releaseCorporateQaLock());
  for (const tab of tabs) await tab.getByRole('button', {name: 'Recuperar operación pendiente'}).waitFor();
  const races = await Promise.all(tabs.map(tab => tab.evaluate(() => window.__corporateQaEvidenceV2())));
  assert.equal(races.reduce((count, evidence) => count + evidence.requests.length, 0), 1,
    'Two queued tabs must not create two different intents');
  assert.equal(races.reduce((count, evidence) => count + evidence.effects, 0), 1);
  console.log('Two real browser tabs share one journal and one Web Lock: passed');
  await context.close();

  const failurePage = await browser.newPage();
  failurePage.setDefaultTimeout(10000);
  await failurePage.goto(baseUrl + '/login');
  await setup(failurePage, {latestFailure: true});
  await failurePage.goto(baseUrl + '/purchases');
  await failurePage.getByText('REM-UI-001', {exact: true}).first().click();
  await failurePage.getByRole('textbox', {name: 'Cantidad a recibir'}).first().fill('0.5');
  failurePage.once('dialog', dialog => dialog.accept());
  await failurePage.getByRole('button', {name: 'Recibir', exact: true}).first().click();
  await failurePage.getByRole('button', {name: 'Recuperar operación pendiente'}).click();
  await failurePage.getByRole('alert').getByText('Operación confirmada.', {exact: false}).waitFor();
  assert.equal(await failurePage.evaluate(() => localStorage.getItem('corporate-intent:v1:org-qa:actor-qa')), null);
  assert.equal((await failurePage.evaluate(() => window.__corporateQaEvidenceV2())).effects, 1);
  assert.equal(await failurePage.getByRole('button', {name: 'Recuperar operación pendiente'}).count(), 0);
  console.log('Confirmed POST with failed detail refresh does not resurrect uncertain intent: passed');
} finally {
  await browser.close();
}
