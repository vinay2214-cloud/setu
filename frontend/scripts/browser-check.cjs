const { chromium } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({headless:true});
 const context = await browser.newContext({viewport:{width:1280,height:720}});
 const page = await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.SETU_URL || 'http://localhost:3000';
 await context.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
 let ready=false;
 for(let attempt=0;attempt<90;attempt++) {
   try { const health=await context.request.get(`${base}/api/v1/health`,{timeout:1500});if(health.ok()){ready=true;break;} } catch {}
   await new Promise(resolve=>setTimeout(resolve,1000));
 }
 assert(ready,'API did not become ready before browser checks');
 const out=path.resolve(__dirname,'../../artifacts');fs.mkdirSync(out,{recursive:true});
 await page.goto(`${base}/login`);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.waitForURL('**/queue');
 const seed=await context.request.post(`${base}/api/v1/demo/seed`,{data:{scenario:'default'}});assert.equal(seed.status(),200);
 await page.reload();
 await page.getByRole('heading',{name:'Today’s priority queue'}).waitFor();
 await page.getByText('Live updates',{exact:true}).waitFor();
 for(let iteration=0;iteration<3;iteration++) {
  if(iteration) await context.request.post(`${base}/api/v1/demo/seed`,{data:{scenario:'default'}});
  const s=await (await context.request.post(`${base}/api/v1/sim/session`,{data:{patient_id:'P001'}})).json();
  const send=async(id,text,quick_reply)=>{const r=await context.request.post(`${base}/api/v1/sim/messages`,{headers:{'X-Sim-Token':s.token},data:{patient_id:'P001',language:'te',client_msg_id:id,text,quick_reply}});assert.equal(r.status(),200);return r.json();};
  await send('browser-missed','లేదు, ఈ రోజు బాగానే ఉన్నాను.','not_taken');
  const start=Date.now();
  const response=await send('browser-swelling','కాళ్ళు కొంచెం వాచాయి.');
  assert(response.alerts.some(a=>a.rule_id==='R-COMBO-01'&&a.severity==='HIGH'));
  const alertRow=page.getByRole('button',{name:/HIGH alert for Ramesh/});
  if(!iteration){await alertRow.waitFor({timeout:2000});console.log(`Live HIGH alert visible in ${Date.now()-start} ms`);assert.equal(await page.getByRole('button',{name:/MEDIUM alert for Ramesh/}).count(),0);await page.getByText(/Ramesh Kumar.*Day 8/).first().waitFor();await page.screenshot({path:path.join(out,'queue-desktop.png'),fullPage:true});await alertRow.click();await page.getByRole('heading',{name:'Evidence',exact:true}).waitFor();await page.screenshot({path:path.join(out,'alert-drawer.png'),fullPage:true});await page.getByRole('button',{name:'Approve call',exact:true}).click();await page.getByRole('button',{name:'Close alert details'}).click();}
  const emergency=await send('browser-emergency','ఛాతీలో నొప్పిగా ఉంది');assert(emergency.replies[0].text.includes('108'));
 }
 await page.goto(`${base}/patients/P001`);await page.getByRole('heading',{name:'Ramesh Kumar',exact:true}).waitFor();await page.getByRole('heading',{name:'Medication adherence',exact:true}).waitFor();
 await page.getByRole('button',{name:'Care plan',exact:true}).click();await page.getByRole('heading',{name:'Current care plan'}).waitFor();
 await page.goto(`${base}/patients/P001/intake`);await page.getByRole('button',{name:'Load sample',exact:true}).click();await page.getByRole('button',{name:'Draft plan',exact:true}).click();await page.getByRole('heading',{name:'2. Review structured plan',exact:true}).waitFor();assert(await page.getByRole('button',{name:'Activate check-ins'}).isDisabled());
 await page.goto(`${base}/sim/P001`);await page.getByText('Setu (demo)',{exact:true}).waitFor();await page.waitForSelector('.sim-bubble');await page.screenshot({path:path.join(out,'simulator-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'simulator-mobile.png'),fullPage:true});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 assert.equal(errors.length,0,errors.join('\n'));
 console.log('PASS: login, hero 3x, live queue, drawer action, patient record, intake gate, desktop/mobile simulator, no page errors.');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
