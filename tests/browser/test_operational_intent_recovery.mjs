import assert from 'node:assert/strict';
import {mkdirSync, writeFileSync} from 'node:fs';

const {chromium} = await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser = await chromium.launch({headless:true,...(process.env.ADMINRETRO_CHROME_PATH
  ? {executablePath:process.env.ADMINRETRO_CHROME_PATH} : {})});
const base = process.env.BRANCH_SCOPE_POS_URL || 'http://127.0.0.1:3001/pos';
const id = n => `018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12,'0')}`;
const branch = {id:id(3),name:'Sucursal sintética',code:'QA',status:'active',timezone:'America/Chihuahua',
  pos_catalog_visuals_enabled:true,business_unit:{id:id(20),name:'QA',code:'QA',unit_type:'store'},
  legal_entity:{id:id(21),name:'QA'},warehouse:null};
const profile = {organization_id:id(1),user:{id:id(2),email:'intent@example.invalid',display_name:'Actor sintético',status:'active'},
  roles:[],permissions:['pos.operate'],scope:{level:'branch',assigned_branch_id:id(3),home_branch_id:id(3),
    allowed_branch_ids:[id(3)],can_select_branch:false,authorization_version:2},active_branch:branch,
  allowed_branches:[branch],pos_modules:{uber_eats:false,didi_food:false,rappi:false,invoicing:false},
  branch_workspace_context_id:null,branch_workspace_secret_version:null,branch_workspace_state:null,
  branch_workspace_context:null,branch_context_reissue_required:true};
mkdirSync('output/playwright/operational-intents',{recursive:true});
const evidence = [];
try {
  for (const width of [1440,390]) for (const [kind,label] of [
    ['order.create','Pedido'], ['cash.shift.open','Apertura de caja'],
    ['cash.shift.close','Cierre de caja'], ['cash.shift.close.register','Cierre de caja'],
    ['cash.movement.compensate','Compensación de caja'],
  ]) {
    const page = await browser.newPage({viewport:{width,height:844}});
    await page.addInitScript(() => localStorage.setItem('auth_token','synthetic-intent-session'));
    let pending = [{id:id(5),kind,branch_id:id(3),state:'applied',resource_id:id(6)}];
    const reads = [], resolutions = [];
    await page.route('**/api/v1/**',async route => {
      const request = route.request(), path = new URL(request.url()).pathname.replace('/api/v1','');
      if (path === '/auth/session') return route.fulfill({json:profile});
      if (path === '/auth/branch-context-reissues') return route.fulfill({status:409,
        json:{detail:{code:'branch_switch_uncertain_command',message:'Recover the pending command'}}});
      if (path === '/operational-intents') {
        reads.push(request.headers()['authorization']); return route.fulfill({json:pending});
      }
      if (path === `/operational-intents/${id(5)}/resolve`) {
        resolutions.push({contextPresent:Boolean(request.headers()['x-branch-context']),body:request.postData()});
        pending=[];
        return route.fulfill({json:{id:id(5),kind,branch_id:id(3),state:'acknowledged',resource_id:id(6)}});
      }
      throw new Error('Unexpected financial or operational request: '+path);
    });
    await page.goto(base+'/',{waitUntil:'domcontentloaded',timeout:60000});
    await page.getByRole('heading',{name:'Recupera las operaciones pendientes'}).waitFor();
    assert.ok(await page.getByRole('button',{name:'Reintentar',exact:true}).isVisible(),
      'The minimum recovery remains available during the workspace error');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    assert.equal(overflow,false,'Recovery panel must fit a narrow viewport');
    await page.screenshot({path:`output/playwright/operational-intents/blocked-${kind}-${width}.png`,fullPage:true});
    await page.getByRole('button',{name:'Recuperar resultado',exact:true}).click();
    await page.getByRole('status').filter({hasText:`${label} confirmado`}).waitFor();
    assert.equal(resolutions.length,1);
    assert.equal(resolutions[0].contextPresent,false,'Recovery must not acquire an unavailable workspace');
    assert.equal(resolutions[0].body,null,'Client does not declare absence or supply financial data');
    await page.screenshot({path:`output/playwright/operational-intents/recovered-${kind}-${width}.png`,fullPage:true});
    evidence.push({width,kind,workspaceErrorRecovery:true,financialRequests:0,resolutions:resolutions.length,
      ownBearer:reads.every(value=>value==='Bearer synthetic-intent-session'),overflow});
    await page.close();
  }
  writeFileSync('output/playwright/operational-intents/evidence.json',JSON.stringify(evidence,null,2));
  console.log('Recovery during workspace denial passed at 1440 and390 without financial send or context acquisition.');
} finally {await browser.close();}
