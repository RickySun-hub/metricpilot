'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';

type Country = { country: string; before_gbp: number; after_gbp: number; delta_gbp: number };
type Report = {
  request_id: string; status: string; summary: string; warnings: string[];
  metrics: { elapsed_ms: number; tool_calls: number; model_calls: number; estimated_cost_usd: number };
  findings: { label: string; value: number; unit: string; evidence_id: string }[];
  evidence: { id: string; tool: string; args: unknown; sql: string; sql_parameters: string[]; result: { countries?: Country[] }; }[];
  retrieval: { id: string; title: string; text: string; method: string; version: string }[];
  dataset: { source_rows: number; hash: string; audit: Record<string, unknown>; source: { url: string; citation: string; license: string; license_url: string } };
};
const examples = ['How did gross positive sales change from October to November 2011?', 'Which countries contributed to the sales change?', 'What data-quality exclusions affect the sales figures?'];
const money = (value: number) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 }).format(value);

export default function Retail() {
  const [question, setQuestion] = useState(examples[0]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  async function analyze(event: FormEvent) {
    event.preventDefault();
    if (request.current || question.trim().length < 3) return;
    const controller = new AbortController(); request.current = controller;
    const timer = setTimeout(() => controller.abort(), 60000);
    setLoading(true); setReport(null); setError('');
    try {
      const response = await fetch('/api/retail/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: question.trim() }), signal: controller.signal });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The real-data investigation could not be completed.');
      setReport(body);
    } catch (failure) {
      setError(failure instanceof Error && failure.name === 'AbortError' ? 'The request timed out. Please try again.' : failure instanceof Error ? failure.message : 'Unable to connect to the API.');
    } finally {
      clearTimeout(timer); request.current = null; setLoading(false);
    }
  }
  const countries = report?.evidence.find(item => item.tool === 'retail_country_contributions')?.result.countries;
  const topCountries = countries ? [...countries].sort((a, b) => Math.abs(b.delta_gbp) - Math.abs(a.delta_gbp)).slice(0, 8) : [];
  const maxContribution = Math.max(1, ...topCountries.map(row => Math.abs(row.delta_gbp)));
  return <main>
    <header className="site-header"><a className="wordmark" href="/">MetricPilot<span className="brand-square" /></a><div className="header-links"><a href="/">Synthetic benchmark</a><a href="https://archive.ics.uci.edu/dataset/352/online%2Bretail" target="_blank" rel="noreferrer">UCI source ↗</a></div></header>
    <section className="hero"><div className="hero-heading"><div className="eyebrow">Real public transaction case study</div><h1>Real records.<br />Traceable sales.</h1><p>Investigate a historical retailer’s sales change with versioned definitions, executed SQL and an explicit data-quality audit.</p></div><aside className="hero-aside"><span className="aside-number">541,909</span><p>Source invoice lines.<br />38 countries.</p><div className="dataset-tag">UCI Online Retail · CC BY 4.0</div><small>Historical public transactions, December 2010–December 2011. No invented signup, visit or experiment events.</small></aside></section>
    <section className="workspace" aria-labelledby="retail-heading"><div className="section-heading"><h2 id="retail-heading">October versus November 2011</h2><span>01</span></div>
      <form onSubmit={analyze}><label className="question-label" htmlFor="retail-question">Your question</label><textarea id="retail-question" minLength={3} maxLength={1000} value={question} onChange={event => setQuestion(event.target.value)} disabled={loading} rows={3} /><div className="form-bottom"><p className="mode-note">Deterministic SQL and local semantic retrieval. No live LLM or paid API calls.</p><button className="primary-button" disabled={loading || question.trim().length < 3}>{loading ? 'Investigating…' : 'Run investigation'}<span aria-hidden="true">→</span></button></div></form>
      <div className="examples">{examples.map((text, index) => <button className="example" disabled={loading} key={text} onClick={() => setQuestion(text)}><span className="example-number">0{index + 1}</span><div><strong>{text}</strong></div><span aria-hidden="true">↗</span></button>)}</div>
      <p className="mode-note">Gross positive sales = quantity × unit price for non-cancelled lines with positive quantity and price. This is not net revenue, profit or business uplift. Questions use a bounded English vocabulary; other dates, metrics and filters are rejected.</p>
    </section>
    {loading ? <section className="loading-state" role="status"><span className="loader" /><p>Retrieving contracts and running the two approved analytical tools.</p></section> : null}
    {error ? <section className="error-state" role="alert"><strong>Unable to complete this request</strong><p>{error}</p></section> : null}
    {report ? <section className="report" aria-live="polite"><div className="section-heading"><h2>{report.status === 'completed' ? 'Investigation complete' : report.status === 'unsupported' ? 'Outside supported data scope' : report.status === 'timed_out' ? 'Request deadline reached' : 'No verified report available'}</h2><span>02</span></div><div className="report-meta"><span>Real public transactions</span><span>Deterministic tools</span><span>{report.metrics.elapsed_ms.toLocaleString()} ms</span></div><p className="summary">{report.summary}</p>
      <div className="finding-grid">{report.findings.map(finding => <div className="finding" key={finding.label}><span>{finding.label}</span><strong>{money(finding.value)}</strong><a href={`#${finding.evidence_id}`}>Inspect supporting evidence</a></div>)}</div>
      {topCountries.length > 0 ? <div className="result-chart"><div className="chart-heading"><h3>Largest country contributions to sales change</h3></div>{topCountries.map(row => <div className="chart-row" key={row.country}><span>{row.country}</span><div className="chart-track"><div className={`chart-bar ${row.delta_gbp < 0 ? 'earlier' : 'later'}`} style={{ width: `${Math.abs(row.delta_gbp) / maxContribution * 100}%` }} /></div><strong>{row.delta_gbp > 0 ? '+' : ''}{money(row.delta_gbp)}</strong></div>)}<p>Bar length shows magnitude; labels preserve the sign. The complete country table is in the evidence.</p></div> : null}
      <div className="warnings"><strong>Interpretation limits</strong><ul>{report.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></div>
      <div className="report-details"><div><h3>Data quality and exclusions</h3><p>Reason counts can overlap. Only excluded_lines counts each rejected source line once; missing IDs and duplicate repetitions are retained.</p><details open><summary>Inspect full-source audit</summary><pre>{JSON.stringify(report.dataset.audit, null, 2)}</pre></details></div><div><h3>Source and execution</h3><p>{report.dataset.source.citation}</p><p><a href={report.dataset.source.url} target="_blank" rel="noreferrer">Original UCI dataset</a> · <a href={report.dataset.source.license_url} target="_blank" rel="noreferrer">{report.dataset.source.license}</a></p><p>{report.dataset.source_rows.toLocaleString()} source invoice lines; {report.metrics.tool_calls} tool calls; {report.metrics.model_calls} model calls</p><p>Source records are aggregated by month and country before bundling. Customer IDs are not served.</p><details><summary>Snapshot fingerprint</summary><code className="fingerprint">{report.dataset.hash}</code></details></div></div>
      <div className="evidence-section"><h3>Executed evidence</h3>{report.evidence.map(item => <details className="evidence" id={item.id} key={item.id}><summary><span>{item.id}</span><strong>{item.tool}</strong></summary><div className="evidence-body"><h4>Tool arguments</h4><pre>{JSON.stringify(item.args, null, 2)}</pre><h4>Ordered SQL parameters</h4><pre>{JSON.stringify(item.sql_parameters, null, 2)}</pre><h4>Executed SQL</h4><pre>{item.sql}</pre><h4>Exact tool result</h4><pre>{JSON.stringify(item.result, null, 2)}</pre></div></details>)}</div>
      <div className="definitions"><h3>Retrieved metric contracts</h3>{report.retrieval.map(item => <details key={item.id}><summary>{item.title}<span>{item.id}</span></summary><p>{item.text}</p><small>{item.method} · version {item.version}</small></details>)}</div>
    </section> : null}
    <footer><strong>MetricPilot</strong><p>Public-data case study. AI-assisted implementation. Descriptive findings, not causal business impact.</p><a href="/">Explore the synthetic validation suite ↗</a></footer>
  </main>;
}
