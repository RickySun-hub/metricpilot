'use client';

import { FormEvent, useEffect, useState } from 'react';

type Evidence = { id: string; tool: string; args: unknown; sql?: string | null; result: unknown; warnings?: string[]; elapsed_ms?: number };
type Report = {
  request_id: string; status: string; mode: string; question: string; summary: string;
  findings: { label: string; value: number | string; unit?: string; evidence_id?: string }[];
  evidence: Evidence[]; trace: { step: string; detail: string }[];
  retrieval: { id: string; title: string; text: string; score?: number }[];
  metrics: { elapsed_ms: number; model_calls: number; tool_calls: number; input_tokens: number; output_tokens: number; estimated_cost_usd: number };
  dataset: { hash: string; users: number; events: number; label: string; cutoff: string };
  warnings: string[];
};
const examples = [
  {name: 'Activation', question: 'Why did activation fall between the two weeks?', detail: 'Compare rates and channel composition.'},
  {name: 'Funnel', question: 'Where did the signup to practice completion funnel change?', detail: 'Inspect each step and its denominator.'},
  {name: 'Experiment validity', question: 'Is experiment onboarding_srm trustworthy?', detail: 'Check assignment before interpreting effects.'},
  {name: 'Experiment effect', question: 'Should we ship onboarding_valid?', detail: 'Inspect effect size and uncertainty.'},
];
const statusLabels: Record<string,string> = { completed: 'Investigation complete', needs_clarification: 'More detail needed', unsupported: 'Outside supported scope', invalid_data: 'Data validity check failed', budget_exceeded: 'Request budget reached', provider_error: 'Model provider unavailable', timed_out: 'Request deadline reached' };
const stringify = (value: unknown) => JSON.stringify(value, null, 2);

function Findings({ findings }: {findings: Report['findings']}) {
  return <div className="finding-grid">{findings.map((finding,index) => <div className="finding" key={`${finding.label}-${index}`}>
    <span>{finding.label}</span><strong>{typeof finding.value === 'number' ? finding.value.toLocaleString(undefined,{maximumFractionDigits: 4}) : finding.value}<small>{finding.unit ? ` ${finding.unit}` : ''}</small></strong>
    {finding.evidence_id && <a href={`#evidence-${finding.evidence_id}`}>Evidence {finding.evidence_id}</a>}
  </div>)}</div>;
}

function EvidenceChart({ evidence }: {evidence: Evidence[]}) {
  const item = evidence.find(e => e.tool==='compare_metric' || e.tool==='analyze_funnel');
  if (!item || !item.result || typeof item.result !== 'object') return null;
  const result = item.result as {before?: Record<string,number>;after?:Record<string,number>};
  if (!result.before || !result.after) return null;
  const funnel = item.tool==='analyze_funnel';
  const keys = funnel ? ['users','started','completed'] : ['rate'];
  const rows = keys.flatMap(key=>['before','after'].map(period=>({label:`${period==='before'?'Earlier':'Later'} ${funnel ? key : 'activation'}`,value:Number(result[period as 'before'|'after']?.[key]) * (funnel?1:100)})));
  if (rows.some(row=>!Number.isFinite(row.value))) return null;
  const max = funnel ? Math.max(1,...rows.map(row=>row.value)) : 100;
  return <div className="result-chart"><div className="chart-heading"><h3>{funnel?'Funnel counts':'Activation by signup cohort'}</h3><a href={`#evidence-${item.id}`}>Source: {item.id}</a></div>{rows.map((row,index)=><div className="chart-row" key={row.label}><span>{row.label}</span><div className="chart-track"><div className={`chart-bar ${index%2===0?'earlier':'later'}`} style={{width:`${Math.max(0,row.value/max*100)}%`}} /></div><strong>{row.value.toLocaleString(undefined,{maximumFractionDigits:2})}{funnel?'':'%'}</strong></div>)}<p>{funnel?'User counts with complete observation windows.':'Percentage of eligible signups completing a practice session within seven days. Scale: 0–100%.'}</p></div>;
}

export default function Home() {
  const [question,setQuestion] = useState(examples[0].question);
  const [mode,setMode] = useState<'deterministic'|'live'>('deterministic');
  const [health,setHealth] = useState<{live_enabled:boolean;status:string}|null>(null);
  const [report,setReport] = useState<Report|null>(null);
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState('');
  const [evaluation,setEvaluation] = useState<unknown>(null);
  useEffect(() => {
    fetch('/api/health').then(r => {if (!r.ok) throw new Error();return r.json();}).then(setHealth).catch(() => setHealth(null));
    fetch('/api/evaluation').then(r => r.ok ? r.json() : null).then(setEvaluation).catch(() => setEvaluation(null));
  },[]);
  async function analyze(event: FormEvent) {
    event.preventDefault(); if (loading || !question.trim()) return;
    setLoading(true);setError('');setReport(null);
    const controller = new AbortController();const timer = setTimeout(() => controller.abort(),90000);
    try {
      const response = await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question: question.trim(),mode,dataset:'demo'}),signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The investigation could not be completed. Please try again.');
      setReport(data);
    } catch (failure) {setError(failure instanceof Error && failure.name === 'AbortError' ? 'The request timed out. Try deterministic tools or a narrower question.' : failure instanceof Error ? failure.message : 'Unable to connect to the API.');}
    finally {clearTimeout(timer);setLoading(false);}
  }
  return <main>
    <header className="site-header"><a className="wordmark" href="/">MetricPilot<span className="brand-square" /></a><div className="header-links"><a href="/retail">Real transactions</a><a href="#how-it-works">How it works</a><a href="https://github.com/RickySun-hub/metricpilot" target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a></div></header>
    <section className="hero"><div className="hero-heading"><div className="eyebrow">Product analytics investigation</div><h1>Ask a question.<br/>Inspect the evidence.</h1><p>Investigate metric changes, funnel drop-offs, and experiment validity with SQL and statistical tools you can verify.</p></div><aside className="hero-aside"><span className="aside-number">01—03</span><p>Metrics.<br/>Funnels.<br/>Experiments.</p><div className="dataset-tag">Synthetic SaaS dataset</div><small>No real user data. Findings describe this dataset, not a real business.</small></aside></section>
    <section className="workspace" aria-labelledby="investigate-heading"><div className="section-heading"><h2 id="investigate-heading">Start an investigation</h2><span>01</span></div>
      <form onSubmit={analyze}><label className="question-label" htmlFor="question">Your question</label><textarea id="question" maxLength={1200} value={question} onChange={e=>setQuestion(e.target.value)} disabled={loading} rows={3} />
        <div className="form-bottom"><fieldset disabled={loading}><legend>Execution mode</legend><div className="mode-options"><label className={mode==='deterministic'?'selected':''}><input type="radio" name="mode" checked={mode==='deterministic'} onChange={()=>setMode('deterministic')} />Deterministic tools</label><label className={mode==='live'?'selected':''}><input type="radio" name="mode" checked={mode==='live'} disabled={!health?.live_enabled} onChange={()=>setMode('live')} />Live LLM</label></div></fieldset><button className="primary-button" type="submit" disabled={loading || !question.trim()}>{loading ? 'Investigating…' : 'Run investigation'}<span aria-hidden="true">→</span></button></div>
        <p className="mode-note">{mode==='deterministic' ? 'Runs supported analytical tools without an LLM. This mode is not an agent simulation.' : 'The model selects bounded tools; numerical results come from SQL and Python.'}{!health?.live_enabled && ' Live LLM is unavailable on this instance.'}</p>
      </form>
      <div className="examples">{examples.map((example,index)=><button disabled={loading} className="example" key={example.name} onClick={()=>setQuestion(example.question)}><span className="example-number">0{index+1}</span><div><strong>{example.name}</strong><span>{example.detail}</span></div><span aria-hidden="true">↗</span></button>)}</div>
    </section>
    {loading && <section className="loading-state" role="status"><span className="loader" /><div><strong>Running the investigation</strong><p>Retrieving definitions and executing validated tools. Results appear when checks finish.</p></div></section>}
    {error && <section className="error-state" role="alert"><strong>Unable to complete this request</strong><p>{error}</p></section>}
    {report && <section className="report" aria-live="polite"><div className="section-heading"><h2>{statusLabels[report.status] || report.status}</h2><span>02</span></div><div className="report-meta"><span>{report.mode==='live'?'Live LLM':'Deterministic tools'}</span><span>Request {report.request_id}</span><span>{report.metrics.elapsed_ms.toLocaleString()} ms</span></div><h3 className="report-question">{report.question}</h3><p className="summary">{report.summary}</p>
      {report.warnings?.length>0 && <div className="warnings"><strong>Interpretation notes</strong><ul>{report.warnings.map((warning,index)=><li key={index}>{warning}</li>)}</ul></div>}
      {report.findings?.length>0 && <Findings findings={report.findings} />}
      <EvidenceChart evidence={report.evidence || []} />
      <div className="report-details"><div><h3>Execution record</h3><ol className="trace">{report.trace?.map((step,index)=><li key={index}><strong>{step.step}</strong><p>{step.detail}</p></li>)}</ol></div><div><h3>Dataset & request</h3><dl><dt>Dataset</dt><dd>{report.dataset.label}</dd><dt>Records</dt><dd>{report.dataset.users.toLocaleString()} users / {report.dataset.events.toLocaleString()} events</dd><dt>Cutoff</dt><dd>{report.dataset.cutoff}</dd><dt>Tool / model calls</dt><dd>{report.metrics.tool_calls} / {report.metrics.model_calls}</dd><dt>Model tokens</dt><dd>{report.metrics.input_tokens} input / {report.metrics.output_tokens} output</dd><dt>Estimated model cost</dt><dd>${Number(report.metrics.estimated_cost_usd).toFixed(6)}</dd></dl><details><summary>Dataset fingerprint</summary><code className="fingerprint">{report.dataset.hash}</code></details></div></div>
      <div className="evidence-section"><h3>Evidence <span>SQL and exact tool outputs</span></h3>{report.evidence?.map(item=><details className="evidence" key={item.id} id={`evidence-${item.id}`}><summary><span>{item.id}</span><strong>{item.tool}</strong><span>{item.elapsed_ms === undefined ? 'Inspect' : `${item.elapsed_ms.toFixed(1)} ms`}</span></summary><div className="evidence-body"><h4>Parameters</h4><pre>{stringify(item.args)}</pre>{item.sql && <><h4>Executed SQL</h4><pre>{item.sql}</pre></>}<h4>Tool result</h4><pre>{stringify(item.result)}</pre>{item.warnings?.map((warning,index)=><p key={index}>{warning}</p>)}</div></details>)}</div>
      {report.retrieval?.length>0 && <div className="definitions"><h3>Retrieved definitions</h3>{report.retrieval.map(definition=><details key={definition.id}><summary>{definition.title}<span>{definition.id}</span></summary><p>{definition.text}</p></details>)}</div>}
    </section>}
    <section className="how-it-works" id="how-it-works"><div className="section-heading"><h2>A conclusion is only as useful as its evidence.</h2><span>03</span></div><div className="principles"><article><span>01</span><h3>Define the metric</h3><p>Retrieve the denominator, observation window, and analysis unit before calculating a result.</p></article><article><span>02</span><h3>Run bounded tools</h3><p>Validated parameters drive SQL and statistical calculations. Tool outputs stay available for inspection.</p></article><article><span>03</span><h3>Respect uncertainty</h3><p>Data checks and confidence intervals constrain conclusions. Descriptive changes do not establish causality.</p></article></div>
      <details className="evaluation"><summary>Evaluation results<span>Inspect measured results</span></summary>{evaluation ? <pre>{stringify(evaluation)}</pre> : <p>Evaluation results are unavailable on this instance. See the repository for the evaluation protocol and recorded results.</p>}</details>
    </section><footer><strong>MetricPilot</strong><p>A public analytical engineering project. Synthetic data; bounded analytical scope.</p><a href="https://github.com/RickySun-hub/metricpilot" target="_blank" rel="noreferrer">Source & limitations ↗</a></footer>
  </main>;
}
