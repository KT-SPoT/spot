// Execute the actual exported Code node scripts without a running n8n instance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const workflow = JSON.parse(fs.readFileSync(path.join(__dirname, '../workflows/n8n/spot-research-api.json'), 'utf8'));
const byName = Object.fromEntries(workflow.nodes.map(n => [n.name,n]));
function run(name, input) {
  return new Function('$json','$execution','$now',byName[name].parameters.jsCode)(input,{id:'synthetic-42'},
    {setZone:zone=>{assert.equal(zone,'Asia/Seoul');return {toISODate:()=> '2026-10-01'};}})[0].json;
}
const normalized = run('Normalize request',{body:{store:{name:'Synthetic',address:'Synthetic'},
  campaign:{purpose:'Synthetic',product:'Synthetic'},research:{lookback_days:0}}});
assert.equal(normalized.valid,true);
assert.equal(normalized.request.research.lookback_days,0);
assert.equal(normalized.request.research.reference_date,'2026-10-01');
assert.equal(normalized.request.request_id,'spot-n8n-synthetic-42');
assert.equal(run('Normalize request',{body:{}}).statusCode,422);
assert.equal(run('Normalize request',{body:[]}).valid,false);
assert.equal(run('Validate job ID',{query:{job_id:'a'.repeat(32)}}).valid,true);
for (const job_id of ['../secret','https://other.example','bad',null]) {
  assert.equal(run('Validate job ID',{query:{job_id}}).statusCode,422);
}
assert.equal(workflow.active,false);
for (const [source, ports] of Object.entries(workflow.connections)) {
  assert.ok(byName[source]);
  for (const branch of ports.main) for (const edge of branch) assert.ok(byName[edge.node]);
}
for (const node of workflow.nodes.filter(n=>n.type.endsWith('.httpRequest'))) {
  assert.equal(node.parameters.genericAuthType,'httpHeaderAuth');
  assert.equal(node.retryOnFail,false);
  assert.equal(node.parameters.options.response.response.fullResponse,true);
  assert.equal(node.parameters.options.response.response.neverError,true);
  assert.equal(node.credentials,undefined);
}
for (const node of workflow.nodes.filter(n=>n.type.endsWith('.webhook'))) {
  assert.equal(node.parameters.authentication,'headerAuth');
  assert.equal(node.parameters.responseMode,'responseNode');
}
console.log('n8n export: normalization, validation, wiring and credential boundaries passed.');
