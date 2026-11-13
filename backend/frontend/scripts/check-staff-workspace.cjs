/* Exercise the built screen routes against isolated read-only test fixtures.
   This checks screen navigation, field state, dialogs and mutation guards;
   it does not certify the deferred business workflows. */
const { chromium } = require('@playwright/test');
const http = require('http');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const screens = require('../src/components/staff-workspace/screens.json');
const root = path.resolve(__dirname, '../build');
const fixture={id:'ui-fixture-1',name:'UI Test Customer',title:'UI Test Property',email:'ui@example.invalid',phone:'+675 70000000',status:'active',account_category:'STAFF',role:'system_admin',customer_type:'seller',created_at:'2026-11-12T00:00:00Z'};
const mime={'.js':'application/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.html':'text/html','.json':'application/json'};
const server=http.createServer((req,res)=>{
  let name=decodeURIComponent(req.url.split('?')[0]);let file=path.resolve(root,'.'+name);
  if(!file.startsWith(root+path.sep))file=path.join(root,'index.html');
  if(!fs.existsSync(file)||!fs.statSync(file).isFile())file=path.join(root,'index.html');
  res.setHeader('Content-Type',mime[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res);
});
(async()=>{
 await new Promise(resolve=>server.listen(4178,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();const errors=[];let writes=0;
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('png_token','isolated-ui-fixture'));
 await page.route('**/api/**',route=>{
  const request=route.request();if(request.method()!=='GET'){writes++;return route.fulfill({status:400,json:{detail:'Writes are disabled in the isolated UI fixture'}});}
  const url=new URL(request.url());let data=[fixture];
  if(url.pathname.endsWith('/auth/me'))data=fixture;
  else if(url.pathname.endsWith('/reports/summary'))data={properties_active:1,leads_new:1,inspections_open:0,tasks_open:0,customers:1,requirements_active:0,properties_sold:0,properties_leased:0};
  else if(url.pathname.includes('/content/'))data={value:{agency_name:'TRELPNG'}};
  else if(url.pathname.includes('/communications'))data=[];
  return route.fulfill({json:data});
 });
 for(const s of screens){
  await page.goto(`http://127.0.0.1:4178${s.route}?screen=${s.key}`);
  await page.locator(`[data-screen="${s.key}"]`).waitFor();
  await page.getByRole('heading',{name:s.title,exact:true}).first().waitFor();
  if(s.kind==='popup'){
   const dialog=page.getByRole('dialog',{name:s.title,exact:true});assert(await dialog.isVisible(),s.key+' dialog is missing');
   await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  }
  assert.equal(errors.length,0,`${s.key}: ${errors.join('; ')}`);
 }
 // Text entered on one form remains available after its related-screen round trip.
 await page.goto('http://127.0.0.1:4178/admin/customers?screen=customerform');
 await page.locator('#sw-customerform-full-name').fill('Unsaved UI customer');
 await page.getByRole('button',{name:'Check duplicates',exact:true}).click();
 await page.getByRole('dialog',{name:'Review possible customer duplicate',exact:true}).waitFor();
 await page.keyboard.press('Escape');
 assert.equal(await page.locator('#sw-customerform-full-name').inputValue(),'Unsaved UI customer');
 assert(await page.getByRole('button',{name:'Save customer',exact:true}).isDisabled());
 // Actual record IDs, rather than sample IDs, survive a list-to-detail transition.
 await page.goto('http://127.0.0.1:4178/admin/customers');
 await page.getByRole('button',{name:'Open record',exact:true}).first().click();
 assert(new URL(page.url()).searchParams.get('recordId')===fixture.id);
 assert(new URL(page.url()).searchParams.get('recordType')==='customers');
 // Invalid context is explicit rather than falling through to a different screen.
 await page.goto('http://127.0.0.1:4178/admin/customers?screen=propertyprice');
 await page.getByRole('heading',{name:'Screen unavailable'}).waitFor();
 // Filtering and the scrollable mobile menu remain usable.
 await page.goto('http://127.0.0.1:4178/admin/customers');
 await page.getByLabel('Search records',{exact:true}).fill('does-not-exist');
 await page.getByText('No records are available in this view.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Reset filters',exact:true}).click();
 await page.getByRole('button',{name:'Open record',exact:true}).first().waitFor();
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Open staff menu',exact:true}).click();
 await page.getByTestId('sidebar-group-administration').click();
 await page.getByRole('link',{name:'Users & Permissions',exact:true}).click();
 await page.getByRole('heading',{name:'Users & Permissions',exact:true}).waitFor();
 assert(await page.getByTestId('admin-sidebar').isHidden());
 assert.equal(writes,0,'New screen navigation must not write business data');
 assert.equal(errors.length,0,errors.join('; '));
 console.log(`PASS: ${screens.length} screen routes; popup Escape/return; in-memory form retention; actual record context; filters; mobile menu; no business writes.`);
 await browser.close();server.close();
})().catch(error=>{console.error(error);server.close();process.exit(1);});
