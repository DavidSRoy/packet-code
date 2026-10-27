import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const read = file => readFileSync(new URL('../public/' + file, import.meta.url), 'utf8');
function runtime() {
  const node = { addEventListener() {} };
  const context = { localStorage: { getItem() { return null; }, setItem() {} }, innerWidth:1400,
    document: { querySelector() { return node; }, addEventListener() {} },
    structuredClone, URL, console, setTimeout, clearTimeout };
  vm.createContext(context);
  vm.runInContext(read('research-data.js'), context);
  vm.runInContext(read('canvas.js').replace(/\nshell\(\);\s*$/, ''), context);
  return expression => vm.runInContext(expression, context);
}
test('research records have unique IDs and safe source links', () => {
  const run=runtime();
  assert.equal(run(`Object.values(researchData).every(rows => new Set(rows.map(r=>r.id)).size===rows.length)`),true);
  assert.equal(run(`Object.values(researchData).flat().every(r=>!r.source_url || safeUrl(r.source_url).startsWith('https://'))`),true);
  assert.equal(run('researchData.operators.length'),8);
  assert.equal(run(`researchData.articles.filter(r=>r.status==='Reviewed').length`),29);
});
test('IBIS observations preserve units and forecast distinction', () => {
  const run=runtime();
  assert.equal(run(`researchData.market.find(r=>r.year===2026).revenue`),44.3135);
  assert.equal(run(`researchData.market.find(r=>r.year===2031).revenue`),68.7504);
  assert.equal(run(`researchData.market.find(r=>r.year===2027).period`),'Forecast');
});
test('widget calculations omit missing measures rather than treating them as zero',()=>{
 const run=runtime();
 assert.equal(run(`groupRows({x:'group',y:'value',agg:'sum'},[{group:'A',value:null}]).length`),0);
 assert.equal(run(`groupRows({x:'group',y:'value',agg:'avg'},[{group:'A',value:4},{group:'A',value:null},{group:'A',value:8}])[0].value`),6);
 assert.equal(run(`groupRows({x:'group',y:'count',agg:'count'},[{group:'A'},{group:'A'}])[0].value`),2);
});
test('CSV ingestion handles commas, multiline fields and numeric values',()=>{
 const run=runtime(),csv='name,note,payload\r\n"Demo, aircraft","line 1\nline 2",6.6\r\n';
 assert.equal(run(`csvParse(${JSON.stringify(csv)})[0].name`),'Demo, aircraft');
 assert.equal(run(`csvParse(${JSON.stringify(csv)})[0].payload`),6.6);
 assert.equal(run(`csvParse(${JSON.stringify(csv)})[0].note`),'line 1\nline 2');
 assert.throws(()=>run(`csvParse('name,name\\nA,B')`),/unique column/);
});
test('unsafe URLs and financial assets stay outside the active application',()=>{
 const run=runtime();
 assert.equal(run(`safeUrl('javascript:alert(1)')`),'');
 assert.equal(run(`safeUrl('https://www.faa.gov/uas')`),'https://www.faa.gov/uas');
 assert.doesNotMatch(read('index.html'),/packet-model|dashboard\.js|app\.js/);
});
