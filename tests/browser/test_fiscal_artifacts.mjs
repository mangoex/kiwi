// SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-fiscal-artifacts-browser-v1
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';
const {chromium}=await import(process.env.ADMINRETRO_PLAYWRIGHT_IMPORT || 'playwright');
const browser=await chromium.launch({headless:true,...(process.env.ADMINRETRO_CHROME_PATH
  ?{executablePath:process.env.ADMINRETRO_CHROME_PATH}:{})});
const base=(process.env.ADMINRETRO_BASE_URL||'http://127.0.0.1:3003/admin').replace(/\/$/,'');
const id=n=>`018f6f73-2d0a-74f0-8f1c-${String(n).padStart(12,'0')}`;
const out='output/playwright/fiscal-artifacts';mkdirSync(out,{recursive:true});
const evidence={reader:null,configurator:null};
function profile(capability){
  return {organization_id:id(1),user:{id:id(2),display_name:'QA Fiscal',email:'fiscal@example.invalid',status:'active'},
    roles:[],permissions:[capability],admin_capabilities:{[capability]:true},
    active_branch:{id:id(3),name:'QA Centro',code:'QA-A',status:'active',timezone:'America/Chihuahua'},
    allowed_branches:[{id:id(3),name:'QA Centro',code:'QA-A',status:'active'}],
    scope:{level:capability==='invoicing.config.manage'?'organization':'branch',allowed_branch_ids:[id(3)],
      assigned_branch_id:id(3),authorization_version:1},pos_modules:{},branch_workspace_state:null,
    ...(capability==='invoicing.read'?{branch_context_reissue_required:true,branch_workspace_context_id:null,
      branch_workspace_secret_version:null,branch_workspace_context:null}:{})};
}
async function open(capability,viewport){
  const page=await browser.newPage({viewport});page.setDefaultTimeout(15000);
  await page.addInitScript(()=>localStorage.setItem('auth_token','qa-fiscal-bearer'));
  const requests=[],saves=[],dialogs=[];
  const versions=new Map([[id(30),1],[id(31),0]]);
  page.on('dialog',async dialog=>{dialogs.push(dialog.message());await dialog.dismiss();});
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname.replace('/api/v1','');
    requests.push({path,method:request.method(),authorization:request.headers().authorization,
      context:request.headers()['x-branch-context']});
    if(path==='/auth/session')return route.fulfill({json:profile(capability)});
    if(path==='/auth/branch-context-reissues')return route.fulfill({json:{...profile(capability),
      branch_workspace_state:'active',branch_workspace_context_id:id(4),branch_workspace_secret_version:1,
      branch_workspace_context:'qa-fiscal-reader-context-'+'x'.repeat(32),branch_context_reissue_required:false}});
    if(path==='/invoicing/emitters')return route.fulfill({json:[
      {id:id(30),name:'QA Emisor A',tax_id:'SYN010101AAA'},
      {id:id(31),name:'QA Emisor B',tax_id:'BBB010101BBB'}]});
    if(path.match(/^\/invoicing\/emitters\/[^/]+\/configuration$/)){
      const emitter=path.split('/')[3];
      if(request.method()==='PUT'){
        const payload=request.postDataJSON();
        assert.equal(payload.expected_version,versions.get(emitter));
        saves.push({...payload,emitter});versions.set(emitter,versions.get(emitter)+1);
      }
      return route.fulfill({json:{id:versions.get(emitter)?id(40):null,
        organization_id:id(1),legal_entity_id:emitter,version:versions.get(emitter),
        is_enabled:emitter===id(30),environment:emitter===id(30)?'sandbox':'',api_key_configured:emitter===id(30),
        api_key:'qa-legacy-secret-must-not-hydrate',organization_legal_name:'QA Emisor',
        organization_rfc:'SYN010101AAA',organization_zip:'80000',organization_tax_system:'601',
        default_product_sat_key:'90101501',default_unit_sat_key:'E48',series:'F',
        enable_self_invoicing:false,self_invoicing_domain:'',self_invoicing_days_valid:30,print_qr_on_ticket:false}});
    }
    if(path.endsWith('/test-connection'))return route.fulfill({json:{success:false,message:'No se pudo verificar la conexión.'}});
    if(path==='/invoicing/invoices')return route.fulfill({json:['issued','pending','cancellation_pending','needs_review'].map((status,n)=>({
      id:id(10+n),folio_number:`QA-${n}`,uuid_sat:n===0||n===2?id(20+n):null,
      rfc_receptor:'SYN010101AAA',nombre_receptor:'QA Receptor',total_cents:1999,currency:'MXN',status,
      created_at:'2026-10-13T18:00:00Z',pdf_url:n===0?'https://attacker.invalid/signed-private':null,xml_url:null,
    }))});
    if(path===`/invoicing/invoices/${id(10)}/pdf`)return route.fulfill({
      contentType:'application/pdf',body:Buffer.from('%PDF-synthetic-browser'),
      headers:{'Content-Disposition':`attachment; filename="factura-${id(10)}.pdf"`}});
    return route.fulfill({status:403,json:{detail:{code:'unexpected_ui_query'}}});
  });
  await page.goto(base+'/integrations',{waitUntil:'domcontentloaded'});
  return {page,requests,saves,dialogs,advanceEmitter:(emitter,version)=>versions.set(emitter,version)};
}
try{
  for(const width of [1440,390]){
    const {page,requests}=await open('invoicing.read',{width,height:900});
    await page.getByRole('heading',{name:'Comprobantes Fiscales Digitales (CFDI 4.0)',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Guardar Configuración',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Configuración Fiscal & API',exact:true}).count(),0);
    assert.equal(await page.getByText('Cancelación pendiente',{exact:true}).count(),1);
    assert.equal(await page.getByText('Pendiente',{exact:true}).count(),1);
    assert.equal(await page.getByText('Revisión requerida',{exact:true}).count(),1);
    assert.equal(await page.getByText('Cancelada',{exact:true}).count(),0);
    const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Descargar PDF de QA-0',exact:true}).click()]);
    assert.equal(download.suggestedFilename(),`factura-${id(10)}.pdf`);
    assert.equal(requests.filter(r=>r.path.endsWith('/pdf')).length,1);
    assert.equal(requests.find(r=>r.path.endsWith('/pdf')).authorization,'Bearer qa-fiscal-bearer');
    assert.equal(requests.find(r=>r.path.endsWith('/pdf')).context,'qa-fiscal-reader-context-'+'x'.repeat(32));
    assert.equal(requests.filter(r=>r.path==='/auth/branch-context-reissues').length,1);
    assert.ok(!requests.some(r=>r.path==='/integrations/facturapi/config'||r.path.startsWith('/integrations/uber')||r.path==='/branches'));
    assert.equal(await page.locator('a[href*="attacker.invalid"]').count(),0);
    await page.screenshot({path:`${out}/reader-${width}.png`,fullPage:true});
    evidence.reader={authenticated_download:true,no_config_or_delivery_queries:true,states_distinct:true};
    await page.close();
  }
  const {page,requests,saves,dialogs,advanceEmitter}=await open('invoicing.config.manage',{width:390,height:900});
  const key=page.getByLabel('Nueva clave de Facturapi',{exact:true});await key.waitFor();
  const emitter=page.getByLabel('Razón social emisora',{exact:true});
  assert.equal(await emitter.inputValue(),'','The issuer must be selected explicitly');
  assert.ok(await key.isDisabled());
  assert.ok(await page.getByRole('button',{name:'Guardar Configuración',exact:true}).isDisabled());
  assert.ok(!requests.some(r=>r.path.endsWith('/configuration')));
  await emitter.selectOption(id(30));await page.getByText('Versión 1.',{exact:false}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Historial de Facturas',exact:true}).count(),0);
  assert.equal(await key.inputValue(),'','Stored/legacy secret never hydrates the form');
  assert.equal(await page.getByText('Clave configurada',{exact:true}).count(),1);
  assert.ok(!requests.some(r=>r.path==='/invoicing/invoices'));
  await key.fill('sk_test_qa_explicit_new_secret');
  await page.getByRole('button',{name:'Guardar Configuración',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[aria-label="Nueva clave de Facturapi"]')?.value==='');
  assert.equal(saves[0].api_key,'sk_test_qa_explicit_new_secret');assert.ok(!('api_key_configured' in saves[0]));
  assert.equal(saves[0].expected_version,1);assert.equal(saves[0].emitter,id(30));
  await page.getByText('Versión 2.',{exact:false}).waitFor();
  await Promise.all([page.waitForResponse(response=>response.url().endsWith(`/emitters/${id(30)}/configuration`)
    &&response.request().method()==='PUT'),page.getByRole('button',{name:'Guardar Configuración',exact:true}).click()]);
  await page.getByText('Configuración guardada.',{exact:true}).waitFor();
  assert.equal(saves.length,2);assert.ok(!('api_key' in saves[1]),'Blank preserves stored credential');
  assert.equal(saves[1].expected_version,2);
  await page.getByText('Versión 3.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Probar Conexión',exact:true}).click();
  await page.getByText('No se pudo verificar la conexión.',{exact:false}).waitFor();
  await key.fill('sk_test_pending_before_external_revision');
  advanceEmitter(id(30),4);
  await page.evaluate(()=>{
    Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});
    window.dispatchEvent(new Event('visibilitychange'));
  });
  await page.evaluate(()=>{
    Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});
    window.dispatchEvent(new Event('visibilitychange'));
  });
  await page.getByRole('button',{name:'Recargar configuración',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'Guardar Configuración',exact:true}).isDisabled());
  assert.equal(await key.inputValue(),'sk_test_pending_before_external_revision');
  assert.equal(saves.length,2,'A refreshed external version cannot silently rebase a draft');
  await page.getByRole('button',{name:'Recargar configuración',exact:true}).click();
  assert.equal(await key.inputValue(),'','Explicit reload discards the old pending credential');
  await page.getByText('Versión 4.',{exact:false}).waitFor();
  await key.fill('sk_test_pending_for_a');
  await emitter.selectOption(id(31));await page.getByText('Versión 0.',{exact:false}).waitFor();
  assert.equal(await key.inputValue(),'','Switching issuers clears the pending key');
  assert.ok(await page.getByRole('button',{name:'Probar Conexión',exact:true}).isDisabled());
  await emitter.selectOption(id(30));await page.getByText('Versión 4.',{exact:false}).waitFor();
  await key.fill('qa-pending-credential');
  await page.evaluate(()=>localStorage.setItem('auth_token','qa-other-account'));
  await page.getByRole('button',{name:'Guardar Configuración',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'La sesión cambió'}).waitFor();
  assert.equal(saves.length,2,'A changed account cannot send a form from the old session');
  assert.ok(!dialogs.some(message=>message.includes('secret')));
  assert.ok(!requests.some(r=>r.path.startsWith('/integrations/facturapi')),'No legacy unbound configuration route');
  await page.screenshot({path:`${out}/configurator-390.png`,fullPage:true});
  evidence.configurator={secret_not_hydrated:true,blank_preserves:true,replacement_cleared:true,
    account_switch_blocked:true,explicit_issuer:true,expected_version:true,issuer_switch_clears_key:true,
    provider_failure_not_reported_as_success:true,external_revision_requires_explicit_reload:true};
  await page.close();
  writeFileSync(`${out}/evidence.json`,JSON.stringify(evidence,null,2)+'\n');
  console.log('Fiscal artifact browser: reader permissions, distinct states, authenticated PDF, private-key form and account switch verified at 1440/390.');
}finally{await browser.close();}
