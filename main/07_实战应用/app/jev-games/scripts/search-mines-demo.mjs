import {spawnSync} from 'node:child_process';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
mkdirSync('captures/mines-search',{recursive:true});
const runs=[];
for(let seed=11;seed<=40;seed++){
 const path=resolve(`captures/mines-search/seed-${seed}.json`);
 const run=spawnSync(process.execPath,['scripts/capture-mines-pair.mjs',String(seed),'70','baseline',path],{encoding:'utf8'});
 if(run.status!==0)throw Error(run.stderr);
 const d=JSON.parse(readFileSync(path,'utf8'));
 const summary={seed,steps:d.baseline.events.length,end:d.baseline.endReason};runs.push(summary);
 console.log(JSON.stringify(summary));writeFileSync('captures/mines-search/summary.json',JSON.stringify(runs,null,2));
 if(d.baseline.error)throw Error(d.baseline.error);
 if(summary.steps>=10){writeFileSync('captures/mines-search/selected.txt',path);break;}
}
