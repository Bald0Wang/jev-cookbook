import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {evaluateTeacher} from './teachers.mjs';

// Local-only provider credentials. Every mutation is an append-only dataset/journal write.
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, x, i, all) => {
  if (x.startsWith('--')) acc.push([x.slice(2), all[i + 1]]);
  return acc;
}, []));
const dir = args['input-dir'];
if (!dir) throw new Error('Usage: --input-dir DIR [--budget-usd 3 --max-requests 3000 --concurrency 8]');
const budget = Number(args['budget-usd'] ?? 3), cap = Number(args['max-requests'] ?? 3000), concurrency = Number(args.concurrency ?? 8);
const maxFailures = Number(args['max-failures'] ?? 1);
if (!Number.isInteger(maxFailures) || maxFailures < 1 || maxFailures > 20) throw new Error('Invalid failure limit');
if (!(budget > 0 && budget <= 25) || !Number.isInteger(cap) || cap < 1 || !Number.isInteger(concurrency) || concurrency < 1 || concurrency > 16) throw new Error('Invalid limits');
const outfile = path.join(dir, 'labeled.jsonl'), journalfile = path.join(dir, 'label_journal.jsonl');
const sha = r => createHash('sha256').update(JSON.stringify({state:r.state, questions:r.questions})).digest('hex');
async function lines(file) {
  try {return (await fs.readFile(file, 'utf8')).split('\n').filter(Boolean).map(JSON.parse);}
  catch (e) {if (e.code === 'ENOENT') return []; throw e;}
}
const rows = (await Promise.all(['train','dev','calibration','test','ood'].map(s => lines(path.join(dir, `${s}.jsonl`))))).flat();
if (!rows.length || new Set(rows.map(r => r.id)).size !== rows.length) throw new Error('Empty dataset or duplicate IDs');
const existing = new Map((await lines(outfile)).map(r => [r.id, r]));
const journal = await lines(journalfile), unresolved = new Set();
for (const event of journal) {
  if (event.status === 'started') unresolved.add(event.id);
  else unresolved.delete(event.id);
}
for (const id of existing.keys()) unresolved.delete(id);
if (unresolved.size) throw new Error('Unresolved prior requests: reconcile provider credits and journal before restarting');
for (const r of rows) if (existing.has(r.id) && existing.get(r.id).input_sha256 !== sha(r)) throw new Error('Saved input changed; use a new directory');
let spent = [...existing.values()].reduce((sum,r) => sum + Number(r.teacher.provider_metadata.gateway.cost), 0);
if (!Number.isFinite(spent)) throw new Error('Saved cost is invalid');
const priorFailures = new Set(journal.filter(e => e.status === 'failed').map(e => e.id));
const pending = rows.filter(r => !existing.has(r.id) && !(args['skip-prior-failures'] === 'true' && priorFailures.has(r.id)));
let next = 0, reserved = 0, completed = 0, attempted = 0, failed = 0, stopReason = null;
let writeQueue = Promise.resolve();
const append = (file, value) => {
  writeQueue = writeQueue.then(() => fs.appendFile(file, JSON.stringify(value)+'\n'));
  return writeQueue;
};
const started = new Date().toISOString();
async function worker() {
  while (!stopReason && next < pending.length) {
    const row = pending[next];
    // Conservative application reservation, not a provider-enforced dollar cap.
    const reserve = Math.max(0.002, (Buffer.byteLength(JSON.stringify({state:row.state,questions:row.questions}))+8192)*0.042/1e6);
    if (attempted >= cap || spent + reserved + reserve > budget) {stopReason='application_limit'; break;}
    next++; attempted++; reserved += reserve;
    await append(journalfile, {id:row.id,status:'started',input_sha256:sha(row),at:new Date().toISOString()});
    try {
      const teacher = await evaluateTeacher({teacher:'jev',model:'typesafe-ai/jev',state:row.state,questions:row.questions});
      const cost = Number(teacher.provider_metadata?.gateway?.cost);
      if (!Number.isFinite(cost) || cost < 0) throw new Error('missing_cost');
      spent += cost;
      await append(outfile, {...row,input_sha256:sha(row),teacher,labeled_at:new Date().toISOString()});
      await append(journalfile, {id:row.id,status:'succeeded',cost_usd:cost,at:new Date().toISOString()});
      completed++;
      if (completed % 100 === 0) console.log(JSON.stringify({completed,attempted,pending_total:pending.length,cost_usd:spent}));
    } catch (error) {
      failed++; if (failed >= maxFailures) stopReason='provider_or_persistence_error_limit';
      await append(journalfile, {id:row.id,status:'failed',error_code:String(error.code ?? 'REQUEST_FAILED'),unknown_cost:true,at:new Date().toISOString()});
      console.error(JSON.stringify({id:row.id,error_code:String(error.code ?? 'REQUEST_FAILED'),automatic_retry:false}));
    } finally {reserved -= reserve;}
  }
}
await Promise.all(Array.from({length:concurrency},worker));
await writeQueue;
const summary = {started,finished:new Date().toISOString(),dataset_states:rows.length,dataset_questions:rows.reduce((s,r)=>s+Object.keys(r.questions).length,0),previous_states:existing.size,new_states:completed,attempted,failed,prior_failed_requests:journal.filter(e=>e.status==='failed').length,provider_cost_usd:spent,application_budget_usd:budget,unknown_failed_request_cost:failed>0||priorFailures.size>0,complete:existing.size+completed===rows.length,stop_reason:stopReason,concurrency,max_failures:maxFailures,automatic_retries:0};
await fs.writeFile(path.join(dir,'label_summary.json'),JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify(summary));
if (!summary.complete) process.exitCode=1;
