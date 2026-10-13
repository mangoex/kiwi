// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-corporate-remediation-v1
export default async (page, { latestFailure = false, seedStorage = true } = {}) => {
  const branch = { id: 'branch-qa', name: 'Centro QA', code: 'QA', status: 'active' };
  const permissions = ['branch.admin.access', 'admin.manage', 'purchases.read', 'purchases.manage',
    'purchases.corporate.read', 'purchases.corporate.manage', 'inventory.read'];
  const session = { organization_id: 'org-qa',
    user: { id: 'actor-qa', email: 'qa@example.test', display_name: 'Auditor QA', status: 'active' },
    roles: [{ id: 'role-qa', name: 'Administrador corporativo', scope: 'organization', branch_id: null }],
    permissions, admin_capabilities: Object.fromEntries(permissions.map(code => [code, true])),
    scope: { level: 'organization', assigned_branch_id: branch.id, allowed_branch_ids: [branch.id] },
    active_branch: branch, allowed_branches: [branch] };
  const allocation = id => ({ id, branch_id: branch.id, warehouse_id: 'warehouse-qa',
    quantity: '10.000000', received_quantity: '0.000000', pending_quantity: '10.000000',
    base_quantity: '20.000000', received_base_quantity: '0.000000' });
  const order = { id: 'order-qa', legal_entity_id: 'entity-qa', supplier_id: 'supplier-qa',
    folio: 'REM-UI-001', order_date: '2026-10-13', currency: 'MXN', total: '500',
    status: 'APPROVED', version: 2, lines: [
      { id: 'line-pan', item_id: 'item-pan', presentation_id: 'presentation-pan', quantity: '10',
        presentation_snapshot: { name: 'Caja de pan', item_name: 'Pan brioche', item_sku: 'PAN',
          base_unit_id: 'unit-piece', commercial_unit_id: 'unit-box', base_unit_code: 'PZA', commercial_unit_code: 'CAJA' },
        allocations: [allocation('allocation-pan')] },
      { id: 'line-carne', item_id: 'item-carne', presentation_id: 'presentation-carne', quantity: '10',
        presentation_snapshot: { name: 'Bolsa de carne', item_name: 'Carne de res', item_sku: 'CARNE',
          base_unit_id: 'unit-kg', commercial_unit_id: 'unit-bag', base_unit_code: 'KG', commercial_unit_code: 'BOLSA' },
        allocations: [allocation('allocation-carne')] },
    ] };
  const options = { legal_entities: [{ id: 'entity-qa', name: 'Empresa QA' }],
    suppliers: [{ id: 'supplier-qa', commercial_name: 'Proveedor QA' }], presentations: [],
    destinations: [{ branch_id: branch.id, branch_name: branch.name, legal_entity_id: 'entity-qa',
      warehouse_id: 'warehouse-qa', warehouse_name: 'Almacén QA' }] };
  const requests = [];
  let effects = 0;
  await page.exposeFunction('__corporateQaEvidenceV2', () => ({ requests, effects }));
  await page.unrouteAll();
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (path === '/auth/session') return route.fulfill({ json: session });
    if (path === '/corporate-purchases/options') return route.fulfill({ json: options });
    if (path === '/corporate-purchases') return route.fulfill({ json: [order] });
    if (path === '/corporate-purchases/order-qa') {
      if (latestFailure && requests.length === 2) return route.abort('failed');
      return route.fulfill({ json: order });
    }
    if (path === '/corporate-purchases/order-qa/receipts') {
      requests.push({ body: route.request().postData(), key: route.request().headers()['idempotency-key'] });
      if (requests.length === 1) {
        effects = 1;
        order.version = 3; order.status = 'PARTIALLY_RECEIVED';
        order.lines[0].allocations[0].received_quantity = '0.500000';
        order.lines[0].allocations[0].received_base_quantity = '1.000000';
        order.lines[0].allocations[0].pending_quantity = '9.500000';
        return route.abort('failed');
      }
      if (requests[0].body !== requests.at(-1).body || requests[0].key !== requests.at(-1).key)
        return route.fulfill({ status: 409, json: { detail: { code: 'corporate_purchase_idempotency_conflict', message: 'QA intent mismatch' } } });
      const replay = JSON.parse(JSON.stringify(order));
      order.version = 4; order.status = 'RECEIVED';
      order.lines.forEach(line => line.allocations.forEach(row => {
        row.received_quantity = row.quantity; row.pending_quantity = '0.000000';
        row.received_base_quantity = row.base_quantity;
      }));
      return route.fulfill({ json: { order: replay } });
    }
    return route.fulfill({ json: [] });
  });
  if (seedStorage) await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem('auth_token', 'synthetic-qa-token');
  });
}
