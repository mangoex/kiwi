// EXP-001: a real API and built Admin/POS with synthetic data only.
import assert from 'node:assert/strict';
import {readFileSync, mkdirSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {checkExpenseReadOnlyPresentation} from './operating_expense_access.mjs';

const manifest = JSON.parse(readFileSync(process.env.EXP001_E2E_MANIFEST,'utf8'));
assert.equal(manifest.synthetic_only,true);
const origin = process.env.EXP001_BASE_URL || 'http://127.0.0.1:8148';
assert.equal(new URL(origin).hostname,'127.0.0.1');
const {chromium} = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({headless:true,...(process.env.ADMINRETRO_CHROME_PATH ? {executablePath:process.env.ADMINRETRO_CHROME_PATH} : {})});
const context = await browser.newContext({viewport:{width:1440,height:1000}});
const page = await context.newPage();
page.setDefaultTimeout(20000);
const errors = [];
page.on('pageerror',error=>errors.push(error.message));
mkdirSync('output/playwright',{recursive:true});
try {
  await page.goto(origin+'/admin/login');
  await page.getByLabel('Correo electrónico').fill(manifest.login.email);
  await page.getByLabel('Contraseña').fill(manifest.login.password);
  await page.getByRole('button',{name:'Iniciar Sesión'}).click();
  await page.waitForURL(/\/admin\/?$/);
  await page.evaluate(branch=>{localStorage.setItem('admin_branch_id',branch);localStorage.setItem('pos_branch_id',branch);},manifest.branch_id);
  const token = await page.evaluate(()=>localStorage.getItem('auth_token'));
  const headers = {Authorization:'Bearer '+token};
  const api = async (path,body) => {
    const result = await page.request.post(origin+'/api/v1'+path,{headers:{...headers,'Idempotency-Key':randomUUID()},data:body});
    if (path === '/cash/shifts/open' && result.status() === 409 && (await result.json()).detail.code === 'cash_shift_already_open') return;
    assert.ok(result.ok(),await result.text()); return result.json();
  };
  await api('/cash/shifts/open',{branch_id:manifest.branch_id,register_id:'CAJA-01',opening_cash_cents:200000});
  const beforeStock = await (await page.request.get(origin+'/api/v1/inventory/costs?branch_id='+manifest.branch_id,{headers})).json();
  const name = 'Luz QA '+Date.now();
  await page.goto(origin+'/admin/expense-concepts');
  const workspace = page.locator('.expense-shell');
  await workspace.getByLabel('Código',{exact:true}).fill('LUZ-'+Date.now());
  await workspace.getByLabel('Nombre',{exact:true}).fill(name);
  await workspace.getByRole('button',{name:'Guardar concepto'}).click();
  await workspace.locator('.expense-row').filter({hasText:name}).waitFor();
  await Promise.all([page.waitForResponse(r=>r.url().includes('/api/v1/expenses?') && r.ok()), workspace.getByRole('link',{name:'Ver gastos'}).click()]);
  for (const method of ['cash','transfer']) {
    await workspace.getByRole('button',{name:'Nuevo gasto',exact:true}).click();
    const form = workspace.locator('form').filter({has:page.getByRole('button',{name:'Guardar borrador'})});
    await form.getByLabel('Concepto',{exact:true}).selectOption({label:name});
    await form.getByLabel('Fecha del comprobante').fill('2026-10-08');
    await form.getByLabel('Importe total MXN').fill(method === 'cash' ? '300' : '1000');
    await form.getByLabel('Medio de pago',{exact:true}).selectOption(method);
    await form.getByLabel('Referencia',{exact:true}).fill('RECIBO-'+method);
    await form.getByLabel('Referencias de evidencia (una por línea)').fill('archivo:recibo-'+method);
    await form.getByRole('button',{name:'Guardar borrador'}).click();
    const confirm = workspace.getByRole('button',{name:'Confirmar gasto',exact:true});
    await confirm.waitFor();
    if(method === 'cash') await workspace.getByLabel('Caja',{exact:true}).selectOption('CAJA-01');
    // Lose the successful response after the server commits, then recover after reload.
    if(method === 'cash') await page.route('**/api/v1/expenses/*/confirm',async route=>{
      await route.fetch(); await route.abort('failed');
    },{times:1});
    await confirm.click();
    if(method === 'cash') {
      await workspace.getByRole('button',{name:'Recuperar resultado'}).waitFor();
      await page.reload();
      await workspace.getByRole('button',{name:'Recuperar resultado'}).click();
    }
    await workspace.getByRole('button',{name:'Anular gasto',exact:true}).waitFor();
  }
  const day = new Date().toLocaleDateString('en-CA',{timeZone:'America/Mazatlan'});
  await workspace.getByLabel('Desde',{exact:true}).fill(day);
  await workspace.getByLabel('Hasta',{exact:true}).fill(day);
  await workspace.locator('.expense-metrics').getByText('$1,300.00',{exact:true}).first().waitFor();
  await page.screenshot({path:'output/playwright/exp001-desktop.png',fullPage:true});
  const list = await (await page.request.get(origin+'/api/v1/expenses?branch_id='+manifest.branch_id,{headers})).json();
  assert.equal(list.items.length,2);
  assert.equal(list.items.filter(d=>d.cash_movement_id).length,1);
  const cash = list.items.find(d=>d.payment_method === 'cash');
  await workspace.locator('button.expense-row').filter({hasText:'Efectivo'}).click();
  await workspace.getByRole('button',{name:'Anular gasto',exact:true}).click();
  await workspace.getByLabel('Motivo de anulación').fill('Reembolso real de prueba');
  await workspace.getByLabel('El efectivo fue devuelto a la caja original').check();
  await workspace.getByLabel('Evidencia de devolución').fill('archivo:reembolso-prueba');
  await workspace.getByRole('button',{name:'Confirmar anulación'}).click();
  await workspace.getByText('Registro anulado: Reembolso real de prueba').waitFor();
  const after = await (await page.request.get(origin+'/api/v1/expenses/'+cash.id,{headers})).json();
  assert.ok(after.compensation_movement_id);
  const afterStock = await (await page.request.get(origin+'/api/v1/inventory/costs?branch_id='+manifest.branch_id,{headers})).json();
  assert.deepEqual(afterStock,beforeStock);
  await page.setViewportSize({width:768,height:1024});
  await page.screenshot({path:'output/playwright/exp001-tablet.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true);
  await context.setOffline(true);
  await workspace.getByRole('button',{name:'Nuevo gasto',exact:true}).click();
  const offlineForm = workspace.locator('form').filter({has:page.getByRole('button',{name:'Guardar borrador'})});
  await offlineForm.getByLabel('Concepto',{exact:true}).selectOption({label:name});
  await offlineForm.getByLabel('Fecha del comprobante').fill('2026-10-08');
  await offlineForm.getByLabel('Importe total MXN').fill('25');
  await offlineForm.getByLabel('Medio de pago',{exact:true}).selectOption('other');
  await offlineForm.getByRole('button',{name:'Guardar borrador'}).click();
  await workspace.getByRole('alert').getByText('Necesitas conexión para registrar el gasto.').waitFor();
  assert.equal(await offlineForm.getByLabel('Importe total MXN').inputValue(),'25');
  await context.setOffline(false);
  await workspace.getByRole('button',{name:'Cerrar captura'}).click();
  await page.goto(origin+'/pos/administration');
  await page.locator('a[href*="/admin/expenses?"]').click();
  await page.waitForURL(/\/admin\/expenses\?/);
  assert.equal(new URL(page.url()).searchParams.get('branch_id'),manifest.branch_id);
  await workspace.getByRole('heading',{name:'Gastos',exact:true}).waitFor();
  await checkExpenseReadOnlyPresentation(page);
  assert.deepEqual(errors,[]);
  console.log('EXP-001 browser: catalogue, cash/noncash, uncertain result, refund, inventory unchanged, responsive UI and POS/Admin parity passed');
} catch (error) {
  await page.screenshot({path:'output/playwright/exp001-failure.png',fullPage:true});
  console.error((await page.locator('body').innerText()).slice(-5000));
  throw error;
} finally {await browser.close();}
