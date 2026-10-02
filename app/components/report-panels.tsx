'use client';
import { DatasetKind, Report, dateLabel, funnelRows, isVerifiedNarrative, money, number, openSource, pipelineStages, SavedRecord, sourceLink, usd } from './report-model';
const json = (value: unknown) => JSON.stringify(value, null, 2);
export function SourceAnchor({ id, children }: {
    id: string;
    children: React.ReactNode;
}) {
    return <a href={`#${id}`} onClick={() => openSource(id)}>{children}</a>;
}
export function Narrative({ report }: {
    report: Report;
}) {
    const checked = isVerifiedNarrative(report);
    return <section id="narrative" className="narrative">
    {checked ? <><h3 className="minor-heading">Cited model narrative</h3>{report.claims!.map((claim, index) => <div className="claim" key={index}><p>{claim.text}</p><div className="citation-row">{claim.evidence_ids.map(id => <SourceAnchor key={id} id={`evidence-${id}`}>SQL evidence ↗</SourceAnchor>)}{claim.contract_ids.map(id => <SourceAnchor key={id} id={`definition-${id}`}>{report.retrieval.find(item => item.id === id)?.title || id} ↗</SourceAnchor>)}</div></div>)}</> : <><p>{report.summary}</p><p className="microcopy">{report.mode === 'deterministic' ? 'Deterministic template narrative. No model-generated claims.' : 'No verified model narrative was produced.'}</p></>}
    {checked && <p className="microcopy">Numerical values and citation targets passed checks. Semantic correctness is not automatically verified.</p>}
  </section>;
}
export function ResultChart({ report, dataset }: {
    report: Report;
    dataset: DatasetKind;
}) {
    const rows = funnelRows(report);
    if (rows.length) {
        const max = Math.max(...rows.flatMap(row => [row.before, row.after]), 1);
        return <figure className="analysis-chart"><figcaption><h3>Where the funnel narrows</h3><span>Unique users · complete 7-day observation</span></figcaption><div className="chart-legend"><span><i className="earlier-swatch"/>Earlier cohort</span><span><i className="later-swatch"/>Later cohort</span></div><div className="funnel-plot">{rows.map(row => <div className="funnel-row" key={row.label}><span className="bar-label">{row.label}</span><div className="bar-pair"><div className="bar-line"><div className="bar earlier" style={{ width: `${row.before / max * 100}%` }}/><strong>{number(row.before, 0)}</strong></div><div className="bar-line"><div className="bar later" style={{ width: `${row.after / max * 100}%` }}/><strong>{number(row.after, 0)}</strong></div></div></div>)}</div><p className="chart-note">September 1–8 vs September 8–15, 2026 signup cohorts. <SourceAnchor id={`evidence-${rows[0].evidenceId}`}>Inspect calculation ↗</SourceAnchor></p></figure>;
    }
    const metric = report.evidence.find(item => item.tool === 'compare_metric');
    if (metric && Number.isFinite(metric.result.before?.rate) && Number.isFinite(metric.result.after?.rate)) {
        return <figure className="analysis-chart"><figcaption><h3>Activation by signup cohort</h3><span>Eligible users completing practice within seven days · scale 0–100%</span></figcaption><div className="country-plot">{(['before', 'after'] as const).map((period, index) => <div key={period} className="country-row"><div><span>{index === 0 ? 'Earlier' : 'Later'} cohort</span><strong>{number(metric.result[period].rate * 100)}%</strong></div><div className="country-track"><div className={`bar ${index === 0 ? 'earlier' : 'later'}`} style={{ width: `${metric.result[period].rate * 100}%` }}/></div></div>)}</div><p className="chart-note"><SourceAnchor id={`evidence-${metric.id}`}>Inspect calculation ↗</SourceAnchor></p></figure>;
    }
    const countries = report.evidence.find(item => item.tool === 'retail_country_contributions');
    if (dataset === 'retail' && Array.isArray(countries?.result.countries)) {
        const top = [...countries.result.countries].sort((a, b) => Math.abs(b.delta_gbp) - Math.abs(a.delta_gbp)).slice(0, 6);
        const max = Math.max(...top.map(row => Math.abs(row.delta_gbp)), 1);
        return <figure className="analysis-chart"><figcaption><h3>Country contribution to change</h3><span>October → November 2011 · GBP</span></figcaption><div className="country-plot">{top.map(row => <div key={row.country} className="country-row"><div><span>{row.country}</span><strong>{row.delta_gbp > 0 ? '+' : ''}{money(row.delta_gbp)}</strong></div><div className="country-track"><div className={`bar ${row.delta_gbp < 0 ? 'negative' : 'later'}`} style={{ width: `${Math.abs(row.delta_gbp) / max * 100}%` }}/></div></div>)}</div><p className="chart-note">Largest six contributions by absolute magnitude. Length is magnitude; labels preserve direction. <SourceAnchor id={`evidence-${countries!.id}`}>All countries ↗</SourceAnchor></p></figure>;
    }
    return null;
}
export function Telemetry({ report }: {
    report: Report;
}) {
    const m = report.metrics;
    return <dl className="telemetry"><div><dt>Elapsed</dt><dd>{number(m.elapsed_ms / 1000, 2)}<small> s</small></dd></div><div><dt>Model / tool calls</dt><dd>{m.model_calls}<small> / {m.tool_calls}</small></dd></div><div><dt>Model tokens</dt><dd>{number(m.input_tokens + m.output_tokens, 0)}</dd></div><div><dt>Est. model cost</dt><dd>{usd(m.estimated_cost_usd)}</dd></div></dl>;
}
export function EvidenceTrail({ report, dataset }: {
    report: Report;
    dataset: DatasetKind;
}) {
    const stages = pipelineStages(report, dataset);
    return <aside className="evidence-rail" aria-label="Evidence trail"><h2>Evidence trail</h2><p className="rail-intro">Inspect what actually happened.</p><ol className="pipeline">{stages.map((stage, index) => <li key={stage.key} data-state={stage.state}><a href={`#${stage.target}`} onClick={() => openSource(stage.target)}><span className="step-number">{index + 1}</span><span><strong>{stage.title}</strong><small>{stage.state === 'fixed' ? 'Fixed workflow; no model selection' : stage.state === 'template' ? 'Deterministic template' : stage.state === 'not_recorded' ? 'No completed event recorded' : stage.detail}</small></span><span className="step-mark" aria-label={stage.state === 'recorded' ? 'Recorded' : stage.state}>{stage.state === 'recorded' ? '✓' : '·'}</span></a></li>)}</ol><div className="rail-sources"><h3>Sources <span>{report.retrieval.length + report.evidence.length}</span></h3>{report.retrieval.map(item => <SourceAnchor id={`definition-${item.id}`} key={item.id}><span className="source-symbol">≡</span><span>{item.title}<small>Metric contract · v{item.version || '1.0'}</small></span><span>↗</span></SourceAnchor>)}{report.evidence.map(item => <SourceAnchor id={`evidence-${item.id}`} key={item.id}><span className="source-symbol">▤</span><span>{item.tool.replaceAll('_', ' ')}<small>Executed SQL & exact result</small></span><span>↗</span></SourceAnchor>)}</div><p className="microcopy">Trace events are recorded after execution. No simulated streaming or inferred stage timings.</p></aside>;
}
export function EvidenceDesk({ report, dataset, record }: {
    report: Report;
    dataset: DatasetKind;
    record: SavedRecord | null;
}) {
    return <section className="evidence-desk" aria-labelledby="inspect-heading"><div className="section-intro"><div><span className="section-index">02 / SOURCE RECORD</span><h2 id="inspect-heading">Follow the evidence.</h2></div><p>Every chart, number and cited claim connects to a definition or an executed result.</p></div><div className="desk-columns"><div><section id="evidence"><h3 className="desk-title">Executed SQL <span>{report.evidence.length} tool outputs</span></h3>{report.evidence.map(item => <details id={`evidence-${item.id}`} className="source-detail" key={item.id}><summary><span><strong>{item.tool.replaceAll('_', ' ')}</strong><small>{item.id}</small></span><span className="expand-symbol" aria-hidden="true">+</span></summary><div className="source-body"><h4>Validated arguments</h4><pre>{json(item.args)}</pre>{Boolean(item.sql_parameters) && <><h4>Ordered SQL parameters</h4><pre>{json(item.sql_parameters)}</pre></>}{item.sql && <><h4>Executed SQL template</h4><pre>{item.sql}</pre></>}<h4>Exact tool result</h4><pre>{json(item.result)}</pre>{item.warnings?.map((warning, i) => <p className="microcopy" key={i}>{warning}</p>)}</div></details>)}</section><section id="contracts"><h3 className="desk-title">Retrieved definitions <span>{report.retrieval.length} contracts</span></h3>{report.retrieval.map(item => <details className="source-detail" id={`definition-${item.id}`} key={item.id}><summary><span><strong>{item.title}</strong><small>{item.id} · version {item.version || '1.0'}</small></span><span className="expand-symbol" aria-hidden="true">+</span></summary><div className="source-body"><p>{item.text}</p><p className="microcopy">{item.method?.replaceAll('_', ' ')}{typeof item.score === 'number' ? ` · cosine similarity ${item.score.toFixed(4)}` : ''}. Similarity is retrieval relevance, not answer confidence.</p></div></details>)}</section></div><div><details open className="source-detail" id="execution"><summary><span><strong>Execution record</strong><small>{report.trace.length} recorded events</small></span><span className="expand-symbol" aria-hidden="true">+</span></summary><ol className="event-list">{report.trace.map((event, index) => <li key={index}><span>{String(index + 1).padStart(2, '0')}</span><div><strong>{event.step}</strong><p>{event.detail}</p></div></li>)}</ol></details><details open className="source-detail" id="validation"><summary><span><strong>Verification & boundaries</strong><small>What the checks establish</small></span><span className="expand-symbol" aria-hidden="true">+</span></summary><div className="source-body"><dl className="metadata-list"><dt>Execution status</dt><dd>{report.status.replaceAll('_', ' ')}</dd><dt>Numeric references</dt><dd>{report.generation?.numeric_validation || (report.mode === 'deterministic' ? 'Evidence-derived template' : 'Not recorded')}</dd><dt>Citation references</dt><dd>{report.generation?.citation_validation || 'Not applicable to template'}</dd>{report.generation?.schema_version && <><dt>Generation schema</dt><dd>{report.generation.schema_version}</dd></>}<dt>Semantic entailment</dt><dd>Not automatically verified</dd>{report.model && <><dt>Model</dt><dd>{report.model}</dd></>}</dl>{record && <p className="microcopy">{record.review_note}</p>}{report.generation?.numeric_validation_scope && <p className="microcopy">{report.generation.numeric_validation_scope}</p>}<p className="microcopy">{report.metrics.cost_basis || 'Estimated model API cost; not an invoice or total hosting cost.'}</p></div></details><details className="source-detail"><summary><span><strong>Dataset provenance</strong><small>{dataset === 'retail' ? 'UCI Online Retail · CC BY 4.0' : 'Synthetic SaaS snapshot'}</small></span><span className="expand-symbol" aria-hidden="true">+</span></summary><div className="source-body">{dataset === 'retail' ? <><p>{number(report.dataset.source_rows, 0)} historical invoice lines. Customer IDs are removed before serving aggregate data.</p><p><a href={report.dataset.source?.url}>Original dataset ↗</a> · <a href={report.dataset.source?.license_url}>CC BY 4.0 ↗</a></p><h4>Source audit (reason counts may overlap)</h4><pre>{json(report.dataset.audit)}</pre></> : <p>{number(report.dataset.users, 0)} synthetic users · {number(report.dataset.events, 0)} events. Fully observed through {report.dataset.cutoff?.slice(0, 10)}. No real customers or business impact.</p>}<h4>Snapshot SHA-256</h4><code className="hash">{report.dataset.hash}</code>{record && <p><a href={sourceLink(record.source_path)}>Original recorded artifact ↗</a></p>}</div></details></div></div></section>;
}
