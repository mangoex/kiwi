import assert from 'node:assert/strict';

/** Presentation regression; API authorization is exercised independently in Python. */
export async function checkExpenseReadOnlyPresentation(page) {
  let catalogueRequests = 0;
  const observe = request => {if (request.url().includes('/api/v1/expense-concepts')) catalogueRequests++;};
  page.on('request', observe);
  const limitedProfile = async route => {
    const response = await route.fetch();
    const profile = await response.json();
    for (const code of ['expenses.manage','expenses.cancel','expense.concept.read','expense.concept.manage']) profile.admin_capabilities[code] = false;
    await route.fulfill({response,json:profile});
  };
  await page.route('**/api/v1/auth/session*',limitedProfile);
  try {
    await Promise.all([page.waitForResponse(r=>r.url().includes('/api/v1/expenses?') && r.ok()),page.reload()]);
    const workspace = page.locator('.expense-shell');
    await workspace.locator('button.expense-row').first().waitFor();
    assert.equal(await workspace.getByRole('link',{name:'Conceptos de gasto'}).count(),0);
    assert.equal(await workspace.getByRole('button',{name:'Nuevo gasto',exact:true}).count(),0);
    assert.equal(catalogueRequests,0);
    console.log('EXP-001 read-only presentation: no unauthorized catalogue link/query or write action');
  } finally {page.off('request',observe); await page.unroute('**/api/v1/auth/session*',limitedProfile);}
}
