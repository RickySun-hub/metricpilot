export type DatasetKind = 'synthetic' | 'retail';
export type Evidence = {
    id: string;
    tool: string;
    args: unknown;
    sql?: string;
    sql_parameters?: unknown;
    result: Record<string, any>;
    elapsed_ms?: number;
    warnings?: string[];
};
export type Contract = {
    id: string;
    title: string;
    text: string;
    score?: number;
    method?: string;
    version?: string;
};
export type Report = {
    request_id: string;
    question: string;
    mode: string;
    status: string;
    summary: string;
    evidence: Evidence[];
    retrieval: Contract[];
    trace: {
        step: string;
        detail: string;
    }[];
    findings: {
        label: string;
        value: number | string;
        unit?: string;
        evidence_id?: string;
    }[];
    warnings: string[];
    claims?: {
        text: string;
        fact_ids: string[];
        evidence_ids: string[];
        contract_ids: string[];
    }[];
    citations?: {
        id: string;
        kind: string;
        title: string;
    }[];
    generation?: {
        method?: string;
        numeric_validation?: string;
        citation_validation?: string;
        semantic_validation?: string;
        validation_failure_reason?: string;
        schema_version?: string;
        numeric_validation_scope?: string;
    };
    metrics: {
        elapsed_ms: number;
        model_calls: number;
        tool_calls: number;
        input_tokens: number;
        output_tokens: number;
        estimated_cost_usd: number;
        cost_basis?: string;
    };
    model?: string | null;
    dataset: Record<string, any>;
};
export type SavedRecord = {
    id: string;
    title: string;
    subtitle: string;
    dataset: DatasetKind;
    recorded_at: string;
    recorded_at_precision?: string;
    source_path: string;
    review_note: string;
    report: Report;
};
export type LiveRun = {
    track?: string; scope?: string; unrun?: number; automatic_passes?: number;
    id: string;
    run_at: string;
    source_path: string;
    status: string;
    planned: number;
    attempted: number;
    estimated_cost_usd: number;
    stop_reason: unknown;
    gate: any;
    systems: {
        name: string;
        planned: number;
        attempted: number;
        automatic_passes: number;
        whole_task_passes: number;
        manual_reviews_pending: number;
        estimated_cost_usd: number;
        latency_ms: {
            median?: number;
            p95?: number;
        };
    }[];
    cases: {
        id: string;
        repeat: number;
        system: string;
        status: string;
        automatic_pass: boolean;
        whole_task_pass: boolean | null;
        reason: unknown;
    }[];
};
export type SupplementalStatus = { track: string; status: string; planned: number; recorded: number; source_path: string; reason: string };
export type Showcase = {
    generated_at: string;
    records: SavedRecord[];
    verification: {
        deterministic: any;
        retrieval: any;
        retail: any;
        live_runs: LiveRun[]; primary_live_run_id?: string; supplemental_runs?: LiveRun[]; supplemental_status?: SupplementalStatus[];
    };
};
export const repository = 'https://github.com/RickySun-hub/metricpilot';
export const sourceRef = process.env.NEXT_PUBLIC_SOURCE_REF || 'main';
export const sourceLink = (path: string) => `${repository}/blob/${sourceRef}/${path}`;
export const setupLink = `${sourceLink('README.md')}#run-locally`;
export const number = (value: number, digits = 2) => value.toLocaleString('en-US', { maximumFractionDigits: digits });
export const usd = (value: number) => `$${Number(value || 0).toFixed(6)}`;
export const money = (value: number) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: 2 }).format(value);
export function dateLabel(value: string) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });
}
export function isVerifiedNarrative(report: Pick<Report, 'mode' | 'claims' | 'generation'>) {
    return report.mode === 'live' && !!report.claims?.length && report.generation?.method === 'llm_grounded' && report.generation.numeric_validation === 'passed' && report.generation.citation_validation === 'passed';
}
export function pipelineStages(report: Pick<Report, 'mode' | 'trace' | 'generation'> & {
    status?: string;
}, dataset: DatasetKind) {
    return [
        { key: 'retrieve', title: 'Retrieve definitions', target: 'contracts', detail: 'Versioned metric contracts' },
        { key: 'select', title: 'Select approved tools', target: 'execution', detail: 'Bounded actions and parameters' },
        { key: 'execute', title: 'Execute analytical SQL', target: 'evidence', detail: 'Read-only SQL and statistical tools' },
        { key: 'generate', title: 'Generate cited claims', target: 'narrative', detail: 'Evidence-grounded answer' },
        { key: 'verify', title: 'Verify values & references', target: 'validation', detail: 'Mechanical checks; meaning needs review' },
    ].map(stage => {
        let state = report.trace?.some(event => event.step === stage.key) ? 'recorded' : 'not_recorded';
        if (stage.key === 'select' && dataset === 'retail')
            state = 'fixed';
        if (stage.key === 'generate' && report.mode === 'deterministic')
            state = 'template';
        return { ...stage, state };
    });
}
export function funnelRows(report: Pick<Report, 'evidence'>) {
    const evidence = report.evidence.find(item => item.tool === 'analyze_funnel');
    if (!evidence?.result.before || !evidence.result.after)
        return [];
    return [['users', 'Signed up'], ['started', 'Started practice'], ['completed', 'Completed practice']].map(([key, label]) => ({ label, before: Number(evidence.result.before[key]), after: Number(evidence.result.after[key]), evidenceId: evidence.id }));
}
export function openSource(id: string) {
    const target = document.getElementById(id);
    if (target instanceof HTMLDetailsElement)
        target.open = true;
    target?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
}
