'use client';
import { FormEvent, useEffect, useRef, useState } from 'react';
import rawShowcase from '../data/showcase.json';
import { DatasetKind, dateLabel, money, number, openSource, Report, repository, SavedRecord, Showcase, setupLink, sourceLink } from './report-model';
import { EvidenceDesk, EvidenceTrail, Narrative, ResultChart, Telemetry } from './report-panels';
import EvaluationPanel from './evaluation-panel';
import ArchitecturePanel from './architecture-panel';
const showcase = rawShowcase as unknown as Showcase;
const questionPresets = ['Why did activation fall between the two weeks?', 'Where did the signup to practice completion funnel change?', 'Is experiment onboarding_srm trustworthy?', 'Should we ship onboarding_valid?'];
export default function Dashboard({ initialDataset = 'synthetic' }: {
    initialDataset?: DatasetKind;
}) {
    const initial = showcase.records.find(record => record.dataset === initialDataset) || showcase.records[0];
    const [selectedId, setSelectedId] = useState(initial.id);
    const [view, setView] = useState<'investigate' | 'evaluation' | 'architecture'>('investigate');
    const [localMode, setLocalMode] = useState(false);
    const [canRunLocally, setCanRunLocally] = useState(false);
    const [question, setQuestion] = useState(initial.report.question);
    const [localReport, setLocalReport] = useState<Report | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const request = useRef<AbortController | null>(null);
    const selected = showcase.records.find(record => record.id === selectedId)!;
    const report = localReport || selected.report;
    const record: SavedRecord | null = localReport ? null : selected;
    const dataset = selected.dataset;
    useEffect(() => {
        setCanRunLocally(['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname));
        return () => request.current?.abort();
    }, []);
    function selectRecord(id: string) {
        request.current?.abort();
        request.current = null;
        const next = showcase.records.find(item => item.id === id)!;
        setSelectedId(id);
        setQuestion(next.report.question);
        setLocalReport(null);
        setError('');
        setLoading(false);
        setLocalMode(false);
    }
    async function analyze(event: FormEvent) {
        event.preventDefault();
        if (!canRunLocally || request.current || question.trim().length < 3)
            return;
        const controller = new AbortController();
        request.current = controller;
        setLoading(true);
        setError('');
        const timer = setTimeout(() => controller.abort(), 60000);
        try {
            const response = await fetch(dataset === 'retail' ? '/api/retail/analyze' : '/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: question.trim(), mode: 'deterministic', ...(dataset === 'synthetic' ? { dataset: 'demo' } : {}) }), signal: controller.signal });
            if (!response.headers.get('content-type')?.includes('application/json'))
                throw new Error('The local API is not connected. Start FastAPI and configure METRICPILOT_API_URL using the setup guide.');
            const data = await response.json();
            if (!response.ok)
                throw new Error(typeof data.detail === 'string' ? data.detail : 'The local investigation could not be completed.');
            if (request.current === controller)
                setLocalReport(data);
        }
        catch (failure) {
            if (request.current === controller)
                setError(failure instanceof Error && failure.name === 'AbortError' ? 'Request cancelled or timed out. The previous recorded result remains available.' : failure instanceof Error ? failure.message : 'Unable to reach the local API.');
        }
        finally {
            clearTimeout(timer);
            if (request.current === controller) {
                request.current = null;
                setLoading(false);
            }
        }
    }
    const primaryFindings = localReport ? report.findings.slice(0, 6) : dataset === 'retail' ? report.findings.slice(0, 3) : report.findings.filter(item => ['Before completion', 'After completion'].includes(item.label));
    return <><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><a className="wordmark" href={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/`} aria-label="MetricPilot home"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>MetricPilot</a><nav aria-label="Main navigation">{(['investigate', 'evaluation', 'architecture'] as const).map(item => <button key={item} aria-current={view === item ? 'page' : undefined} onClick={() => setView(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}</nav><a className="github-link" href={repository} target="_blank" rel="noreferrer">GitHub <span aria-hidden="true">↗</span></a></header><main id="main-content"><section className="page-heading"><div><h1>{view === 'investigate' ? 'Evidence, all the way down.' : view === 'evaluation' ? 'Show the work. Measure the result.' : 'Built around verifiable answers.'}</h1><p>{view === 'investigate' ? 'A recorded investigation. Every conclusion has a source.' : view === 'evaluation' ? 'Actual runs, explicit boundaries, and a visible failure record.' : 'From a question to the exact SQL behind its answer.'}</p></div><span className="snapshot-label"><span />Recorded showcase<span className="snapshot-date">{dateLabel(showcase.generated_at)}</span></span></section><div className="prototype-notice"><strong>Research prototype</strong><span>Partial model evaluation. Successful recorded examples do not establish full-protocol accuracy or release readiness.</span><button onClick={() => setView('evaluation')}>Inspect evaluation ↗</button></div>
    {view === 'investigate' ? <><div className="investigation-grid"><aside className="question-rail" aria-label="Investigation selection"><h2>Investigations</h2><div className="record-options">{showcase.records.map(item => <button key={item.id} aria-pressed={selectedId === item.id} onClick={() => selectRecord(item.id)}><span className="record-icon" aria-hidden="true">{item.dataset === 'retail' ? '▤' : '⌁'}</span><span><strong>{item.title}</strong><small>{item.dataset === 'retail' ? 'Real public transactions' : 'Synthetic product analytics'}</small></span></button>)}</div><div className="question-context"><div className="run-kind"><span />{record ? (report.mode === 'live' ? 'Recorded live run' : 'Recorded deterministic run') : 'Current deterministic run'}</div><h3>{record ? selected.report.question : 'Your investigation'}</h3><p>{dataset === 'retail' ? '541,909 source invoice lines · UCI Online Retail' : '12,000 synthetic users · 50,504 events'}</p>{record && <><p className="record-date">Recorded {dateLabel(record.recorded_at)}{record.recorded_at_precision === 'day' ? ' · date only' : ''}</p><a className="primary-action" href="#evidence" onClick={() => openSource('evidence')}>Inspect the evidence <span>↘</span></a><a className="subtle-link" href={sourceLink(record.source_path)}>Original run artifact ↗</a></>}</div><details className="local-workspace" open={localMode} onToggle={event => setLocalMode(event.currentTarget.open)}><summary>Local workspace <span aria-hidden="true">+</span></summary>{localMode && <div>{canRunLocally ? <form onSubmit={analyze}><p className="microcopy">Run the local deterministic tools. No model API calls.</p><label htmlFor="question">Your question</label><textarea id="question" value={question} minLength={3} maxLength={1000} onChange={event => setQuestion(event.target.value)} disabled={loading} rows={4}/>{dataset === 'synthetic' && <div className="local-presets">{questionPresets.map((item, index) => <button type="button" key={item} disabled={loading} onClick={() => setQuestion(item)}>{['Activation', 'Funnel', 'SRM check', 'Experiment'][index]}</button>)}</div>}<button className="primary-action" type="submit" disabled={loading || question.trim().length < 3}>{loading ? 'Running tools…' : 'Run deterministic tools'}<span>→</span></button>{loading && <button className="text-button" type="button" onClick={() => request.current?.abort()}>Cancel request</button>}</form> : <p className="microcopy">Server execution is available on localhost only. This public showcase uses saved results and makes no model calls.</p>}<a className="subtle-link" href={setupLink}>Local setup instructions ↗</a></div>}</details><p className="rail-footnote">Explore the recorded evidence freely. Nothing on this page runs a paid model request.</p></aside>
    <article className="result-panel" aria-live="polite">{loading && <div className="request-message" role="status">Running deterministic tools. Recorded evidence remains below until the request completes.</div>}{error && <div className="request-message error" role="alert">{error}</div>}<div className="result-topline"><span>{localReport ? 'LOCAL DETERMINISTIC INVESTIGATION' : dataset === 'retail' ? 'PUBLIC-DATA CASE STUDY' : 'ORDERED FUNNEL INVESTIGATION'}</span><span className={`status-label ${report.status !== 'completed' ? 'status-warning' : ''}`}>{report.status === 'completed' ? '✓ Complete' : report.status.replaceAll('_', ' ')}</span></div><h2>{localReport ? 'Investigation result' : dataset === 'retail' ? 'A sales change, reconciled.' : 'Fewer users complete the funnel.'}</h2><p className="result-deck">{localReport ? report.question : dataset === 'retail' ? 'An observed change across complete historical months. Each country contribution reconciles to the total.' : 'Compare mature signup cohorts, then follow each claim back to the underlying calculation.'}</p>{primaryFindings.length > 0 && <div className="headline-findings">{primaryFindings.map((finding, index) => <div key={index}><span>{finding.label.replace('Before', 'Earlier').replace('After', 'Later')}</span><strong>{typeof finding.value === 'number' ? (finding.unit === 'GBP' ? money(finding.value) : number(finding.value)) : finding.value}<small>{finding.unit && finding.unit !== 'GBP' ? finding.unit : ''}</small></strong></div>)}</div>}<ResultChart report={report} dataset={dataset}/><Telemetry report={report}/><p className="telemetry-note">{record ? 'One recorded execution, not a model-quality benchmark.' : 'Local tool execution. No model-generated narrative.'}{report.model && ` ${report.model}.`}</p><Narrative report={report}/></article><EvidenceTrail report={report} dataset={dataset}/></div><section className="interpretation-band"><div><span className="section-index">INTERPRETATION</span><h2>Descriptive results. No causal claim.</h2></div><div>{report.warnings.length ? report.warnings.map((warning, index) => <p key={index}>{warning}</p>) : <p>These results describe the observed dataset. They do not establish why the change happened or justify a business decision on their own.</p>}{dataset === 'retail' && <p>Gross positive sales exclude cancelled, nonpositive-quantity and nonpositive-price lines. This metric is not net revenue or profit.</p>}</div></section><EvidenceDesk report={report} dataset={dataset} record={record}/></> : view === 'evaluation' ? <EvaluationPanel data={showcase.verification}/> : <ArchitecturePanel />}
    </main><footer className="app-footer"><span>MetricPilot</span><p>AI-assisted engineering. Evidence-first analysis.</p><div><a href={sourceLink('LICENSE')}>MIT code</a><a href={sourceLink('docs/REAL_DATA.md')}>Data & model attribution</a><a href={repository}>Source ↗</a></div></footer></>;
}
