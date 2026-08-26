#!/usr/bin/env node
/** Execute the cashier journey using only bounded Playwright MCP tools. */

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const pairs = [];
for (let index = 2; index < process.argv.length; index += 1) {
  if (process.argv[index].startsWith('--')) pairs.push([process.argv[index].slice(2), process.argv[index + 1]]);
}
const args = Object.fromEntries(pairs);
for (const required of ['manifest', 'result', 'runtime', 'branch-index']) {
  if (!args[required]) throw new Error(`Missing --${required}`);
}

const manifest = JSON.parse(readFileSync(resolve(args.manifest), 'utf8'));
if (!manifest.synthetic_only || manifest.branch_count !== 7) {
  throw new Error('Refusing to run a non-synthetic or non-seven-branch manifest');
}

const runtimeDir = resolve(args.runtime);
const runtimeRequire = createRequire(resolve(runtimeDir, 'package.json'));
const { Client } = runtimeRequire('@modelcontextprotocol/sdk/client/index.js');
const { StdioClientTransport } = runtimeRequire('@modelcontextprotocol/sdk/client/stdio.js');
const baseUrl = 'http://127.0.0.1:8765';
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [
    resolve(runtimeDir, 'node_modules/@playwright/mcp/cli.js'),
    '--isolated', '--headless', '--browser', 'chrome', '--sandbox',
    '--block-service-workers',
    '--allowed-origins', `${baseUrl};http://localhost:8765`,
    '--output-dir', '.e2e/playwright-output',
  ],
  cwd: process.cwd(),
  stderr: 'pipe',
});

const client = new Client({ name: 'restaurantos-cashier-sales-e2e', version: '1.0.0' });
const callText = async (name, toolArgs) => {
  const response = await client.callTool({ name, arguments: toolArgs });
  const text = response.content
    .filter((item) => item.type === 'text')
    .map((item) => item.text)
    .join('\n');
  if (response.isError) throw new Error(`${name} failed: ${text}`);
  return text;
};

const clickTarget = async (target, element) => {
  return callText('browser_click', { target, element });
};

const clickQuantity = async (target, quantity) => {
  let remaining = quantity;
  while (remaining >= 2) {
    await callText('browser_click', {
      target,
      element: 'Sumar producto en la cuenta',
      doubleClick: true,
    });
    remaining -= 2;
  }
  if (remaining === 1) {
    await callText('browser_click', { target, element: 'Sumar producto en la cuenta' });
  }
};

try {
  await client.connect(transport);
  const { tools } = await client.listTools();
  const names = new Set(tools.map((tool) => tool.name));
  const requiredTools = [
    'browser_navigate', 'browser_find', 'browser_type', 'browser_click',
    'browser_handle_dialog', 'browser_wait_for', 'browser_take_screenshot',
    'browser_console_messages', 'browser_network_requests', 'browser_close',
  ];
  for (const required of requiredTools) {
    if (!names.has(required)) throw new Error(`Pinned MCP server lacks ${required}`);
  }

  const branchIndex = Number(args['branch-index']);
  if (!Number.isInteger(branchIndex) || branchIndex < 0 || branchIndex >= manifest.cashiers.length) {
    throw new Error(`Invalid --branch-index ${args['branch-index']}`);
  }
  const branchResults = [];
  for (const cashier of [manifest.cashiers[branchIndex]]) {
    await callText('browser_navigate', { url: `${baseUrl}/admin/login` });
    await callText('browser_type', {
      target: 'input[type="email"]', element: 'Correo electrónico', text: cashier.email,
    });
    await callText('browser_type', {
      target: 'input[type="password"]', element: 'Contraseña', text: cashier.password,
    });
    await clickTarget('button[type="submit"]', 'Botón Iniciar Sesión');
    // The frontend's dev heuristic redirects nonstandard ports to localhost:3001.
    // The authenticated token is already stored at the tested origin, so return
    // to that origin explicitly before exercising the POS.
    await callText('browser_wait_for', { time: 1 });
    await callText('browser_navigate', { url: `${baseUrl}/pos/settings` });
    await callText('browser_wait_for', { text: 'Cajero QA' });

    await callText('browser_type', {
      target: 'input[placeholder="Ej. Caja 1"]',
      element: 'Identificador de Caja',
      text: cashier.register_id,
    });
    const saveSnapshot = await callText('browser_find', { text: 'Guardar configuración' });
    if (!saveSnapshot.includes('disabled')) {
      await clickTarget('button:has-text("Guardar configuración")', 'Botón Guardar configuración');
    }
    await callText('browser_type', {
      target: 'input[placeholder="500.00"]', element: 'Fondo Inicial', text: '500.00',
    });
    await clickTarget('button:has-text("Abrir Turno")', 'Botón Abrir Turno');
    await callText('browser_wait_for', { text: 'Turno abierto correctamente.' });

    const accounts = [];
    for (const account of manifest.account_matrix) {
      await callText('browser_navigate', { url: `${baseUrl}/pos/` });
      await callText('browser_wait_for', { text: 'La cuenta está vacía' });
      for (let lineIndex = 0; lineIndex < account.lines.length; lineIndex += 1) {
        const line = account.lines[lineIndex];
        const category = line.sku === 'KIWI-SODA' ? 'Bebidas' : 'Comida';
        await callText('browser_wait_for', { text: category });
        await clickTarget(`nav.pos-sale-menu button:has-text("${category}")`, `Categoría ${category}`);
        await callText('browser_wait_for', { text: line.name });
        await clickTarget(`button.pos-sale-product-card:has-text("${line.name}")`, `Producto ${line.name}`);
        if (line.quantity > 1) {
          const plusTarget = `.pos-sale-cart-item:nth-child(${lineIndex + 1}) button[aria-label="Sumar producto"]`;
          await clickQuantity(plusTarget, line.quantity - 1);
        }
      }

      const expectedText = '$' + Math.floor(account.target_cents / 100).toLocaleString('es-MX')
        + '.' + String(account.target_cents % 100).padStart(2, '0');
      await callText('browser_wait_for', { time: 1 });
      const totalSnapshot = await callText('browser_find', { text: 'Total' });
      if (!totalSnapshot.includes(expectedText)) {
        throw new Error(`Displayed total mismatch for ${cashier.branch_code} account ${account.sequence}: expected ${expectedText}; ${totalSnapshot}`);
      }

      await clickTarget('.pos-sale-pay', `Botón Pagar ${expectedText}`);
      const methodLabel = {
        cash: 'Efectivo', debit_card: 'Débito', transfer: 'Transferencia',
      }[account.payment_method];
      await clickTarget(`.pos-payment-grid button:has-text("${methodLabel}")`, `Método ${methodLabel}`);
      const checkoutResponse = await clickTarget('.pos-payment-confirm', `Confirmar cobro ${expectedText}`);
      if (!checkoutResponse.includes('Venta finalizada')) {
        throw new Error(`Checkout did not open success dialog: ${checkoutResponse}`);
      }
      await callText('browser_handle_dialog', { accept: true });
      await callText('browser_wait_for', { text: 'La cuenta está vacía' });
      accounts.push({
        sequence: account.sequence,
        target_cents: account.target_cents,
        displayed_total: expectedText,
        payment_method: account.payment_method,
        success_dialog: true,
      });
    }

    await callText('browser_navigate', { url: `${baseUrl}/pos/settings` });
    await callText('browser_wait_for', { text: 'Cerrar operativamente' });
    await clickTarget(
      'button:has-text("Cerrar operativamente")',
      'Botón Cerrar operativamente',
    );
    await callText('browser_wait_for', {
      text: 'Turno cerrado operativamente. El corte final queda pendiente.',
    });

    branchResults.push({
      branch_id: cashier.branch_id,
      branch_name: cashier.branch_name,
      branch_code: cashier.branch_code,
      cashier_email: cashier.email,
      register_id: cashier.register_id,
      account_count: accounts.length,
      browser_total_cents: accounts.reduce((sum, account) => sum + account.target_cents, 0),
      operational_close_confirmed: true,
      accounts,
    });
  }

  await callText('browser_take_screenshot', {
    type: 'png', scale: 'css', filename: `cashier-sales-branch-${branchIndex + 1}.png`, fullPage: true,
  });
  const consoleErrors = await callText('browser_console_messages', { level: 'error', all: true });
  const networkRequests = await callText('browser_network_requests', { static: false });
  const result = {
    status: 'ok',
    mcp_version: '0.0.79',
    bounded_tools_only: true,
    listed_tools: tools.length,
    branch_results: branchResults,
    console_errors: consoleErrors,
    network_requests: networkRequests,
  };
  const resultPath = resolve(args.result);
  mkdirSync(dirname(resultPath), { recursive: true });
  writeFileSync(resultPath, JSON.stringify(result, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({
    status: 'ok', result: resultPath, branches: branchResults.length,
    accounts: branchResults.reduce((sum, branch) => sum + branch.account_count, 0),
  }));
} finally {
  await client.callTool({ name: 'browser_close', arguments: {} }).catch(() => undefined);
  await client.close().catch(() => undefined);
}
