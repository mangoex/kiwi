// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-mobile-password-browser-v1
// Password literals are synthetic fixtures; this test requires the loopback-only API.
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { randomInt } from 'node:crypto';

const base = process.env.MOBILE_PROFILE_BASE_URL || 'http://127.0.0.1:8158';
assert.equal(new URL(base).hostname, '127.0.0.1', 'Synthetic test must stay on loopback');
const { chromium } = await import(process.env.MOBILE_PROFILE_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({ headless: true,
  ...(process.env.MOBILE_PROFILE_CHROME_PATH ? { executablePath: process.env.MOBILE_PROFILE_CHROME_PATH } : {}),
});
const output = process.env.MOBILE_PROFILE_OUTPUT || 'output/playwright/crm-mobile-journey';
mkdirSync(output, { recursive: true });
try {
  for (const width of (process.env.MOBILE_PROFILE_ADMIN_ONLY ? [] : [390, 320, 1280])) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    const requests = []; page.on('request', request => requests.push(request.url()));
    await page.route('**/api/v1/mobile/branches/*/profile', async route => {
      if (route.request().method() === 'GET') await route.fulfill({ status: 503, json: { detail: { code: 'mobile_access_unavailable' } } });
      else await route.continue();
    });
    await page.goto(base + '/menu/');
    await page.getByRole('heading', { name: 'No pudimos preparar tu acceso' }).waitFor();
    assert.equal(await page.getByLabel('Tu teléfono').count(), 0);
    assert.equal(await page.getByRole('button', { name: 'Entrar', exact: true }).count(), 0);
    await page.unroute('**/api/v1/mobile/branches/*/profile');
    await page.getByRole('button', { name: 'Reintentar acceso' }).click();
    await page.getByRole('heading', { name: 'Bienvenido a Kiwi' }).waitFor();
    await page.getByRole('button', { name: 'Crear cuenta', exact: true }).click();
    assert.ok(!requests.some(url => /\/public\/(catalog|branches\/[^/]+\/catalog)/.test(url)));
    await page.screenshot({ path: join(output, `access-${width}.png`) });
    const phone = '669' + String(randomInt(1000000, 9999999));
    await page.getByLabel('Tu teléfono').fill(phone);
    const password = 'Mi desayuno favorito 2026!';
    await page.getByLabel('Contraseña', { exact: true }).fill(password);
    await page.getByLabel('Confirmar contraseña', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Crear mi cuenta' }).click();
    await page.getByRole('heading', { name: 'Cuéntanos de ti' }).waitFor();
    await page.getByLabel('Nombre completo').fill(`Cliente QA ${width}`);
    await page.getByLabel('Día', { exact: true }).fill('29');
    await page.getByLabel('Mes', { exact: true }).selectOption('2');
    assert.equal(await page.getByLabel('Año (opcional)').inputValue(), '');
    await page.screenshot({ path: join(output, `birthday-${width}.png`) });
    const firstSave = page.waitForResponse(response => response.request().method() === 'PUT' && response.url().endsWith('/profile'));
    await page.getByRole('button', { name: 'Guardar mis datos' }).click();
    const first = await firstSave; assert.ok(first.ok(), await first.text());
    await page.getByRole('button', { name: /Agregar Hamburguesa.*al pedido/ }).first().click();
    await page.getByRole('button', { name: 'Carrito', exact: false }).last().click();
    await page.getByRole('tab', { name: 'Envío', exact: true }).click();
    await page.getByRole('button', { name: 'Agregar o editar domicilio y correo' }).click();
    await page.getByLabel('Correo electrónico').fill('cliente.qa@example.com');
    await page.getByLabel('Completar domicilio de entrega').check();
    for (const [label, value] of [ ['Calle', 'Calle de prueba'], ['Número exterior', '12'],
      ['Número interior (opcional)', '7B'], ['Colonia', 'Centro'], ['Código postal', '82000'],
      ['Ciudad', 'Mazatlán'], ['Municipio', 'Mazatlán'], ['Estado', 'Sinaloa'], ['Referencias (opcional)', 'Timbre verde'] ]) {
      await page.getByLabel(label, { exact: true }).fill(value);
    }
    const save = async () => {
      const done = page.waitForResponse(response => response.request().method() === 'PUT' && response.url().endsWith('/profile'));
      await page.getByRole('button', { name: 'Guardar mis datos' }).click();
      const response = await done; assert.ok(response.ok(), await response.text()); return response.json();
    };
    const address = await save();
    assert.equal(address.addresses.length, 1);
    await page.getByRole('dialog', { name: 'Carrito de compras' }).waitFor();
    assert.equal(await page.getByLabel('Domicilio de entrega').inputValue(), address.addresses[0].id);
    assert.equal(await page.getByRole('tab', { name: 'Envío', exact: true }).getAttribute('aria-selected'), 'true');
    await page.getByRole('button', { name: 'Cerrar carrito' }).click();
    await page.getByRole('button', { name: 'Mi perfil', exact: true }).click();
    await page.getByLabel('Nombre completo').fill(`Cliente QA editado ${width}`);
    const replay = await save();
    assert.equal(replay.addresses.length, 1);
    assert.equal(replay.addresses[0].id, address.addresses[0].id);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(overflow, false, `Profile overflows at ${width}`);
    await page.screenshot({ path: join(output, `profile-${width}.png`), fullPage: true });
    await page.getByRole('button', { name: 'Menú', exact: true }).click();
    await page.getByRole('button', { name: 'Carrito', exact: false }).last().click();
    await page.getByRole('tab', { name: 'Envío', exact: true }).click();
    await page.getByRole('button', { name: 'Agregar o editar domicilio y correo' }).waitFor();
    await page.screenshot({ path: join(output, `delivery-${width}.png`), fullPage: true });
    let rejected = false;
    await page.route('**/api/v1/mobile/branches/*/order-intents', async route => {
      if (!rejected) { rejected = true; await route.fulfill({ status: 503, json: { detail: { code: 'mobile_storage_unavailable' } } }); }
      else await route.continue();
    });
    await page.getByRole('button', { name: /Enviar Pedido/ }).click();
    await page.getByRole('alert').filter({ hasText: /Conservamos tu carrito/ }).waitFor();
    assert.equal(await page.getByRole('button', { name: /Enviar Pedido/ }).count(), 1);
    await page.getByRole('button', { name: /Enviar Pedido/ }).click();
    await page.getByRole('heading', { name: /Esperando confirmación|Solicitud recibida/ }).first().waitFor();
    // A fresh browser session must authenticate by password, without any SMS fixture.
    const returning = await browser.newContext({ viewport: { width, height: 900 } });
    const login = await returning.newPage();
    await login.goto(base + '/menu/');
    await login.getByRole('heading', { name: 'Bienvenido a Kiwi' }).waitFor();
    await login.getByLabel('Tu teléfono').fill(phone);
    await login.getByLabel('Contraseña', { exact: true }).fill('Una contraseña incorrecta');
    await login.getByRole('button', { name: 'Entrar', exact: true }).click();
    await login.getByRole('alert').filter({ hasText: 'El teléfono o la contraseña no son correctos.' }).waitFor();
    await login.getByLabel('Contraseña', { exact: true }).fill(password);
    await login.getByRole('button', { name: 'Entrar', exact: true }).click();
    await login.getByRole('button', { name: 'Mi perfil', exact: true }).click();
    assert.equal(await login.getByLabel('Nombre completo').inputValue(), `Cliente QA editado ${width}`);
    await returning.close();
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Mobile customer journey PASS ${width}px`);
  }
  const manifest = JSON.parse(readFileSync(process.env.MOBILE_PROFILE_MANIFEST ||
    'output/playwright/crm-mobile-ui/manifest.json', 'utf8'));
  assert.equal(manifest.synthetic_only, true);
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  await context.addInitScript(token => localStorage.setItem('auth_token', token), manifest.token);
  const page = await context.newPage();
  await page.goto(base + '/admin/customers');
  await page.getByRole('button', { name: 'Editar', exact: true }).first().click();
  await page.getByText('Cumpleaños (año opcional)', { exact: true }).waitFor();
  await page.getByLabel('Día', { exact: true }).fill('1');
  await page.getByLabel('Mes', { exact: true }).fill('10');
  await page.screenshot({ path: join(output, 'admin-birthday-1366.png') });
  const saved = page.waitForResponse(response => response.request().method() === 'PUT' && /\/customers\//.test(response.url()));
  await page.getByRole('button', { name: 'Guardar Cliente', exact: true }).click();
  const response = await saved;
  assert.ok(response.ok(), await response.text());
  const record = await response.json();
  assert.equal(record.birthday_day, 1);
  assert.equal(record.birthday_month, 10);
  assert.equal(record.birthday_year, null);
  await context.close();
  console.log('Admin birthday editor PASS 1366px');
} finally { await browser.close(); }
