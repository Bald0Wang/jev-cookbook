"""Serial, no-retry runs with durable raw evidence and shared budget gates."""
import hashlib,json,math,os,time
from pathlib import Path
from .adapters.base import DecisionResult
from .budget import BudgetExceeded,finite
from .scoring import score_label,score_task
DEFAULT_RESERVE_USD=.02
class Runner:
 def __init__(self,adapter,ledger,raw_dir,default_reserve_usd=.02,**kwargs):
  self.adapter=adapter;self.ledger=ledger;self.raw_dir=Path(raw_dir).resolve();self.reserve=finite(default_reserve_usd)
  if self.raw_dir.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Raw responses must be outside public repository')
  self.raw_dir.mkdir(parents=True,exist_ok=True)
 def run_task(self,t):
  estimate=self.adapter.reserve_estimate(t);reserve=max(self.reserve,finite(estimate)) if estimate is not None else self.reserve
  rid=self.ledger.reserve(reserve,{'task_id':t.id,'adapter':self.adapter.name})
  # v1.2.2: adapters with a per-rubric setup (ProgramAsWeights loads one compiled program per rubric) do it in
  # prepare(), before the clock: setup is not decision latency. Its time is kept as prepare_s. No other adapter has it.
  prep=None
  if hasattr(self.adapter,'prepare'):
   p0=time.perf_counter()
   try:self.adapter.prepare(t)
   except Exception as e:print('prepare failed:',type(e).__name__,str(e)[:200],flush=True)
   prep=time.perf_counter()-p0
  started=time.perf_counter()
  try:r=self.adapter.run(t)
  except Exception as e:r=DecisionResult(self.adapter.name,False,error=type(e).__name__)
  wall=time.perf_counter()-started
  raw=json.dumps({'request':r.request_body,'response':r.raw,'http_status':r.status},ensure_ascii=False,allow_nan=False).encode()
  digest=hashlib.sha256(raw).hexdigest();rawpath=self.raw_dir/(hashlib.sha256(t.id.encode()).hexdigest()+'.json')
  with rawpath.open('xb')as f:f.write(raw)
  price_in=self.adapter.price_input_per_m;price_out=self.adapter.price_output_per_m;cost=None
  # A route with no billable account (local weights, a public demo, a flat-rate
  # subscription) has no per-token tariff. Its cost stays null rather than 0:
  # unmetered is not free, and a plotted 0 would be a claim we cannot source.
  basis=getattr(self.adapter,'cost_basis','unknown')
  if price_in==0 and price_out==0:cost=0.;basis=getattr(self.adapter,'cost_basis','zero_route_fee_compute_excluded')
  elif r.ok and price_in is not None and price_out is not None:
   i=r.usage.get('input_tokens');o=r.usage.get('output_tokens')
   if isinstance(i,(int,float)) and isinstance(o,(int,float)):
    cost=finite(i)*finite(price_in)/1e6+finite(o)*finite(price_out)/1e6;basis='derived_usage_times_tariff'
  # Unknown/failed billed amount retains reservation. Not a measured price.
  self.ledger.settle(rid,cost if cost is not None else reserve,{'task_id':t.id,'basis':basis})
  if r.ok and r.probs is None and r.probs_source=='label_only_no_calibrated_distribution':scored=score_label(r.label,t)
  else:scored=score_task(r.probs or {},t)if r.ok else {'valid':False,'strict_valid':False,'renormalized':False,'correct':False,'predicted':None}
  return {'task_id':t.id,'family':t.family,'split':t.split,'group':t.group,'ts':time.time(),'status':'ok'if r.ok else'failed','ok':r.ok,'valid':scored['valid'],'correct':scored['correct'],'predicted':scored.get('predicted'),'ordinal_ev':scored.get('ordinal_ev'),'probs':scored.get('probs'),'probs_as_returned':r.probs,'strict_valid':scored.get('strict_valid',False),'renormalized':scored.get('renormalized',False),'probs_source':r.probs_source,'model':r.model,'error':r.error,'schema_error':scored.get('error'),'status_code':r.status,'latency_s':wall,'usage':r.usage,'cost_usd':cost,'cost_basis':basis,'reserved_usd':reserve,'charged_usd':cost if cost is not None else reserve,'raw_sha256':digest,'runtime':r.raw.get('runtime')if isinstance(r.raw,dict)else None,**({'prepare_s':prep} if prep is not None else {})}
 def run_all(self,tasks,progress_every=10,results_path=None,delay_s=0.):
  records=[];errors=0;stream=None
  if results_path:
   path=Path(results_path).resolve()
   if path.is_relative_to(Path(__file__).resolve().parents[1]):raise ValueError('Per-item runs must remain outside public repo')
   path.parent.mkdir(parents=True,exist_ok=True);stream=path.open('x')
  try:
   for i,t in enumerate(tasks,1):
    if delay_s and i>1:time.sleep(delay_s)
    try:r=self.run_task(t)
    except BudgetExceeded as e:print('STOP:',str(e),flush=True);break
    records.append(r)
    if stream:stream.write(json.dumps(r,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
    # v1.1.3: a 422 is the system refusing this input (e.g. over its context limit), not an outage; it counts as a wrong answer, not toward the stop rule
    errors=errors+1 if not r['ok'] and r['status_code']!=422 else 0
    if i%progress_every==0:print(f'{i}/{len(tasks)} completed',flush=True)
    if r['status_code']in(401,403,429) or errors>=3:
     print('STOP: access/rate limit or consecutive infrastructure errors; remaining tasks unattempted',flush=True);break
  finally:
   if stream:stream.close()
  return records
 @staticmethod
 def write_results(records,path):
  p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('x')as f:
   for r in records:f.write(json.dumps(r,allow_nan=False)+'\n')
