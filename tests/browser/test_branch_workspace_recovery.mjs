// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-workspace-browser-v1
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';

const {chromium} = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({headless:true,...(process.env.ADMINRETRO_CHROME_PATH
  ? {executablePath:process.env.ADMINRETRO_CHROME_PATH} : {})});
const base = process.env.BRANCH_SCOPE_POS_URL || 'http://127.0.0.1:3001/pos';
const id = n => `018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12,'0')}`;
const branches = [{id:id(3),name:'QA Centro',code:'QA-A',status:'active'},
  {id:id(5),name:'QA Norte',code:'QA-B',status:'active'}];
mkdirSync('output/playwright/branch-workspace',{recursive:true});

function session(branch, context, version, secret=null, actor=id(2)) {
  return {
    organization_id:id(1),user:{id:actor,email:'workspace@example.invalid',display_name:'QA Workspace',status:'active'},
    roles:[],permissions:['pos.operate','pos.branch.select','orders.create'],admin_capabilities:{},
    scope:{level:'organization',assigned_branch_id:null,home_branch_id:null,allowed_branch_ids:branches.map(b => b.id),can_select_branch:true,authorization_version:1},
    active_branch:branch ? {...branches.find(b => b.id===branch),timezone:'America/Chihuahua',pos_catalog_visuals_enabled:true,
      business_unit:{id:id(20),name:'QA',code:'QA',unit_type:'store'},legal_entity:{id:id(21),name:'QA'},warehouse:null} : null,
    allowed_branches:branches,pos_modules:{uber_eats:false,didi_food:false,rappi:false,invoicing:false},
    branch_selection_required:!branch,branch_workspace_context_id:context,branch_workspace_secret_version:version,
    branch_workspace_state:context ? 'active' : null,branch_workspace_context:secret,branch_context_reissue_required:Boolean(branch),
  };
}

try {
  const page = await browser.newPage({viewport:{width:1440,height:900}});
  page.setDefaultTimeout(15000);
  await page.addInitScript(() => {
    if (!localStorage.getItem('auth_token')) localStorage.setItem('auth_token','qa-workspace-owner');
  });
  let branch = null, context = null, version = null, secret = null, loseSelection = true, rejectSelection = false;
  const selections = [], operations = [];
  await page.route('**/api/v1/**',async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1','');
    if (path === '/operational-intents') return route.fulfill({json:[]});
    if (path === '/auth/session') return route.fulfill({json:session(branch,context,version)});
    if (path === '/auth/branch-selections') {
      selections.push({key:request.headers()['idempotency-key'],body:request.postData()});
      if (rejectSelection) return route.fulfill({status:409,json:{detail:{code:'branch_switch_open_shift',message:'An open shift blocks selection'}}});
      branch=request.postDataJSON().target_branch_id; context=id(10); version=(version || 0)+1;
      secret=`qa-only-memory-secret-${version}-${'z'.repeat(32)}`;
      if (loseSelection) {loseSelection=false;return route.abort('failed');}
      return route.fulfill({json:session(branch,context,version,secret)});
    }
    if (path === '/auth/branch-context-reissues') {
      assert.equal(request.postDataJSON().context_id,context);
      secret=`qa-only-memory-secret-${++version}-${'z'.repeat(32)}`;
      return route.fulfill({json:session(branch,context,version,secret)});
    }
    operations.push({path,context:request.headers()['x-branch-context'],expected:secret});
    return route.fulfill({json:path.includes('cash-shifts/current') ? null : []});
  });
  await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:60000});
  await page.getByRole('heading',{name:'Selecciona tu sucursal de trabajo'}).waitFor();
  assert.equal(operations.length,0,'Owner without home never mounts operational reads');
  assert.equal(await page.getByLabel('Sucursal de trabajo').inputValue(),'');
  await page.screenshot({path:'output/playwright/branch-workspace/owner-required-1440.png'});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'output/playwright/branch-workspace/owner-required-390.png'});
  await page.getByLabel('Sucursal de trabajo').selectOption(id(5));
  await page.getByRole('button',{name:'Confirmar sucursal'}).click();
  await page.getByText('No se confirmó el cambio de sucursal.',{exact:false}).waitFor();
  assert.equal(operations.length,0,'A lost selection result does not mount an unconfirmed branch');
  const journalBefore = await page.evaluate(() => Object.entries(sessionStorage).filter(([key]) => key.startsWith('pos_branch_selection_intent_v2:')));
  assert.equal(journalBefore.length,1);
  await page.getByRole('button',{name:'Reintentar',exact:true}).click();
  await page.getByLabel('Sucursal de trabajo').waitFor();
  assert.equal(await page.getByLabel('Sucursal de trabajo').inputValue(),id(5));
  assert.equal(selections.length,2);
  assert.deepEqual(selections[0],selections[1],'Reload recovers the exact key/body despite GET already reporting B');
  await page.waitForFunction(() => Boolean(document.querySelector('.pos-sale-header')));
  assert.ok(operations.length>0);
  assert.ok(operations.every(command => command.context===command.expected && command.context));
  await page.reload();
  await page.getByLabel('Sucursal de trabajo').waitFor();
  assert.equal(await page.getByLabel('Sucursal de trabajo').inputValue(),id(5));
  assert.equal(selections.length,2);
  assert.equal(version,3,'Reload rotates the same selected context');
  assert.ok(operations.every(command => command.context===command.expected && command.context));
  rejectSelection=true;
  await page.getByPlaceholder('Buscar producto…').fill('captura conservada');
  page.once('dialog',dialog => dialog.accept());
  await page.getByLabel('Sucursal de trabajo').selectOption(id(3));
  await page.getByText('No puedes cambiar de sucursal mientras tu turno está abierto.',{exact:false}).waitFor();
  assert.equal(await page.getByLabel('Sucursal de trabajo').inputValue(),id(5));
  assert.equal(await page.getByPlaceholder('Buscar producto…').inputValue(),'captura conservada','Definitive rejection preserves the original mounted capture');
  assert.equal(version,3);
  const persisted = await page.evaluate(() => JSON.stringify([Object.entries(localStorage),Object.entries(sessionStorage)]));
  assert.equal(persisted.includes('qa-only-memory-secret'),false);
  assert.equal(persisted.includes('pos_branch_selection_intent_v2:'),false,'Confirmed recovery clears the pending journal');
  await page.screenshot({path:'output/playwright/branch-workspace/recovered-390.png',fullPage:true});
  writeFileSync('output/playwright/branch-workspace/evidence.json',JSON.stringify({selections,
    operations:operations.map(command => ({path:command.path,contextConfirmed:command.context===command.expected})),
    secretsPersisted:false},null,2));
  console.log('Owner explicit selection, lost result, frozen replay, reload rotation and current operational headers passed.');

  // Corporate configuration does not acquire POS authority as an access requirement.
  const admin = await browser.newPage();
  admin.setDefaultTimeout(15000);
  await admin.addInitScript(() => localStorage.setItem('auth_token','qa-catalog-only'));
  let reissues=0;
  const catalogOnly={...session(id(3),null,null),permissions:['catalog.manage'],
    admin_capabilities:{'catalog.manage':true,'purchases.manage':true,'pos.operate':false},scope:{level:'organization',assigned_branch_id:null,allowed_branch_ids:branches.map(b=>b.id),authorization_version:1}};
  await admin.route('**/api/v1/**',async route => {
    const path=new URL(route.request().url()).pathname.replace('/api/v1','');
    if (path==='/auth/session') return route.fulfill({json:catalogOnly});
    if (path==='/auth/branch-context-reissues') {reissues++;return route.fulfill({status:403,json:{detail:{code:'permission_denied'}}});}
    assert.equal(route.request().headers()['x-branch-context'],undefined);
    return route.fulfill({json:[]});
  });
  await admin.goto((process.env.ADMINRETRO_BASE_URL || 'http://127.0.0.1:3002/admin')+'/products',{waitUntil:'domcontentloaded',timeout:60000});
  await admin.locator('.productos-window-container').waitFor();
  assert.equal(reissues,0);
  console.log('Definitive 409 preserves mounted capture; catalog-only Admin does not require POS workspace.');

  // Built Admin acquires a workspace for document-only operators on its operational routes.
  for (const [capability,path,title] of [
    ['purchases.manage','/purchases','Compra de sucursal'],
    ['expenses.manage','/expenses','Gastos'],
  ]) {
    const operator=await browser.newPage({viewport:{width:1440,height:900}});
    await operator.addInitScript(()=>localStorage.setItem('auth_token','qa-document-only'));
    const documentProfile={...session(id(3),id(10),1),permissions:[capability,capability.replace('.manage','.read')],
      admin_capabilities:{[capability]:true,[capability.replace('.manage','.read')]:true,'pos.operate':false},
      financial_access:{schema_version:2,authorization_version:1,branches:[{
        branch_id:id(3),policy_version:1,state:'active',capabilities:{},datasets:[],
      }]},
      scope:{level:'branch',assigned_branch_id:id(3),allowed_branch_ids:[id(3)],authorization_version:1}};
    const documentContext='qa-document-browser-context-'+'x'.repeat(32);
    const writes=[],reads=[],documentErrors=[];
    operator.on('pageerror',error=>documentErrors.push(error.message));
    await operator.route('**/api/v*/**',async route=>{
      const request=route.request(),pathname=new URL(request.url()).pathname;
      const endpoint=pathname.replace(/^\/api\/v[12]/,'');
      if(endpoint==='/auth/session')return route.fulfill({json:documentProfile});
      if(endpoint==='/auth/branch-context-reissues'){
        writes.push({body:request.postDataJSON(),key:request.headers()['idempotency-key']});
        return route.fulfill({json:{...documentProfile,branch_context_reissue_required:false,
          branch_workspace_context:documentContext,branch_workspace_secret_version:2}});
      }
      reads.push({endpoint,pathname,context:request.headers()['x-branch-context']});
      return route.fulfill({json:endpoint==='/expenses'?{
        schema_version:2,projection:'operational',policy_version:1,items:[],next_cursor:null,
      }:endpoint.includes('cash-context')?{open_registers:[]}:[]});
    });
    await operator.goto((process.env.ADMINRETRO_BASE_URL||'http://127.0.0.1:3002/admin')+path,
      {waitUntil:'domcontentloaded',timeout:60000});
    await operator.getByRole('heading',{name:title,exact:true}).waitFor();
    await operator.getByText(capability==='purchases.manage'?'No hay compras registradas':'No hay gastos para estos filtros.',{exact:true}).waitFor();
    assert.deepEqual(documentErrors,[]);
    assert.equal(writes.length,1,capability);
    assert.equal(writes[0].body.context_id,id(10));
    assert.ok(writes[0].key);
    assert.ok(reads.length>0);
    assert.ok(reads.every(read=>read.context===documentContext));
    if(capability==='expenses.manage') {
      assert.equal(reads.find(read=>read.endpoint==='/expenses')?.pathname,'/api/v2/expenses');
      assert.deepEqual(documentProfile.financial_access.branches[0].datasets,[]);
    }
    await operator.screenshot({path:'output/playwright/branch-workspace/document-'+capability+'-1440.png',fullPage:true});
    await operator.setViewportSize({width:390,height:844});
    await operator.getByRole('heading',{name:title,exact:true}).waitFor();
    assert.deepEqual(documentErrors,[]);
    await operator.screenshot({path:'output/playwright/branch-workspace/document-'+capability+'-390.png',fullPage:true});
    await operator.close();
  }
  console.log('Built Admin document-only profiles acquire context on purchase/expense routes; current headers at 1440/390.');
} finally {await browser.close();}
