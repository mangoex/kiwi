// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-corporate-remediation-v1
export default async page => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  await page.getByText('REM-UI-001', {exact: true}).first().click();
  const quantity = page.getByRole('textbox', {name: 'Cantidad a recibir'}).first();
  const receive = page.getByRole('button', {name: 'Recibir', exact: true}).first();
  check(await receive.isDisabled(), 'Blank quantity must not receive');
  check((await page.evaluate(() => window.__corporateQaEvidenceV2())).requests.length === 0, 'Blank quantity posted');
  await quantity.fill('0.5');
  await page.evaluate(() => localStorage.setItem('auth_token', 'synthetic-other-actor-token'));
  page.once('dialog', dialog => dialog.accept());
  await receive.click();
  await page.getByRole('alert').getByText('La sesión cambió.', {exact: false}).waitFor();
  check((await page.evaluate(() => window.__corporateQaEvidenceV2())).requests.length === 0, 'Stale authority sent POST');
  check(await page.evaluate(() => localStorage.getItem('corporate-intent:v1:org-qa:actor-qa')) === null, 'Stale authority created journal');
  await page.evaluate(() => localStorage.setItem('auth_token', 'synthetic-qa-token'));
  page.once('dialog', dialog => dialog.accept());
  await receive.click();
  await page.getByRole('button', {name: 'Recuperar operación pendiente'}).waitFor();
  check(await quantity.isDisabled(), 'Uncertain intent allows input editing');
  check(await page.getByRole('button', {name: 'Nueva orden corporativa'}).isDisabled(), 'Uncertain intent allows new command');
  const persisted = await page.evaluate(() => localStorage.getItem('corporate-intent:v1:org-qa:actor-qa'));
  check(Boolean(persisted), 'Lost response discarded journal');
  await page.screenshot({path: 'output/playwright/corporate-uncertain-1440.png', fullPage: true});
  await page.reload();
  await page.getByRole('button', {name: 'Recuperar operación pendiente'}).click();
  await page.getByRole('heading', {name: 'REM-UI-001'}).waitFor();
  await page.getByText('Base — Ordenado: 20.000000 · Recibido: 20.000000 · Pendiente: 0.000000', {exact: true}).first().waitFor();
  const evidence = await page.evaluate(() => window.__corporateQaEvidenceV2());
  check(evidence.requests.length === 2 && evidence.effects === 1, 'Replay must have one synthetic effect');
  check(evidence.requests[0].key === evidence.requests[1].key && evidence.requests[0].body === evidence.requests[1].body, 'Replay changed key/body');
  check(await page.evaluate(() => localStorage.getItem('corporate-intent:v1:org-qa:actor-qa')) === null, 'Resolved journal remains');
  check(await page.getByRole('button', {name: 'Recibir', exact: true}).count() === 0, 'Replay did not refresh latest v4');
  await page.screenshot({path: 'output/playwright/corporate-recovered-1440.png', fullPage: true});
  await page.setViewportSize({width: 390, height: 1000});
  await page.screenshot({path: 'output/playwright/corporate-recovered-390.png', fullPage: true});
  console.log(JSON.stringify({passed: ['blank quantity', 'credential changed before click', 'frozen uncertain input', 'reload replay same key/body', 'latest detail after replay'], evidence}));
}
