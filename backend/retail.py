"""Auditable public transaction analysis; no inferred visits or randomized trials."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

import duckdb
from langgraph.graph import END, START, StateGraph

from .agent import DatasetUnavailableError, REQUEST_TIMEOUT_SECONDS, State, validate_findings
from .retrieval import embedder
from .tools import ToolError

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / 'data' / 'retail_monthly.json'
BEFORE_MONTH, AFTER_MONTH = '2011-10', '2011-11'
CONTRACTS = [
    {'id':'retail_gross_sales','title':'Gross positive sales in GBP','text':
     'Sum Quantity times UnitPrice for invoice lines with positive quantity and price, excluding cancellation invoices starting C. This is gross positive sales, not net revenue, profit, or causal uplift. Missing customer identifiers do not exclude a valid sales line.'},
    {'id':'retail_country','title':'Country contribution to sales change','text':
     'Subtract October 2011 gross positive sales from November 2011 for each country. Country contributions sum to the total change. Countries absent in one month contribute zero in that month. This is an accounting decomposition, not causal attribution.'},
    {'id':'retail_quality','title':'Source and quality boundaries','text':
     'UCI Online Retail by Daqing Chen (2015), DOI 10.24432/C5BW33, CC BY 4.0. Public historical UK retailer transactions from December 2010 to December 2011. Exact duplicate rows are retained and counted because no source line ID proves which repeated lines are erroneous. Only complete October and November 2011 are compared.'},
    {'id':'retail_scope','title':'What transaction records cannot establish','text':
     'Invoices provide no visits, signup events, product funnel, or randomized experiment assignments. Do not infer conversion, SaaS activation, A/B validity, or a causal business effect. Invoice counts are observed orders, not users.'},
]


def load_snapshot() -> dict:
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding='utf-8'))
        expected = payload['hash']
        actual = hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k != 'hash'},
                                          sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if actual != expected:
            raise ValueError('Snapshot checksum mismatch')
        source, audit, monthly = payload['source'], payload['audit'], payload['monthly']
        for key in ('name','url','citation','license','license_url'):
            if not isinstance(source[key],str) or not source[key]:
                raise ValueError('Invalid source metadata')
        for key in ('total_rows','included_lines','excluded_lines','missing_customer_id_lines',
                    'missing_description_lines','exact_duplicate_rows','cancellation_lines',
                    'nonpositive_quantity_lines','nonpositive_price_lines','invalid_lines','country_count'):
            if type(audit[key]) is not int or audit[key] < 0:
                raise ValueError('Invalid source audit')
        if type(source['source_rows']) is not int or source['source_rows'] != audit['total_rows']:
            raise ValueError('Source row count does not reconcile')
        if audit['included_lines'] + audit['excluded_lines'] != audit['total_rows']:
            raise ValueError('Source exclusions do not reconcile')
        groups = set()
        for row in monthly:
            if set(row) != {'month','country','lines','orders','units','gross_sales_gbp'}:
                raise ValueError('Unexpected aggregate fields')
            if not isinstance(row['month'],str) or not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',row['month']):
                raise ValueError('Invalid aggregate month')
            if not isinstance(row['country'],str) or not row['country']:
                raise ValueError('Invalid aggregate country')
            key = (row['month'],row['country'])
            if key in groups:
                raise ValueError('Duplicate month-country group')
            groups.add(key)
            if any(type(row[field]) is not int or row[field] <= 0 for field in ('lines','orders','units')):
                raise ValueError('Invalid aggregate count')
            money = Decimal(row['gross_sales_gbp'])
            if not money.is_finite() or money <= 0 or money >= Decimal('1e18') or money.as_tuple().exponent < -6:
                raise ValueError('Invalid aggregate sales')
        if not monthly or sum(row['lines'] for row in monthly) != audit['included_lines']:
            raise ValueError('Aggregate line counts do not reconcile')
        return payload
    except Exception as exc:
        raise DatasetUnavailableError('The public retail dataset is unavailable. Please try again later.') from exc


def retrieve_contracts(question: str) -> list[dict]:
    model = embedder()
    vectors = model.encode([doc['title']+'. '+doc['text'] for doc in CONTRACTS])
    similarities = (vectors @ model.encode([question])[0]).tolist()
    order = sorted(range(len(CONTRACTS)), key=lambda i: (-similarities[i], CONTRACTS[i]['id']))[:3]
    return [{**CONTRACTS[i], 'score':round(similarities[i],4), 'version':'1.0',
             'method':'minilm_cosine_similarity'} for i in order]


class RetailAnalytics:
    """Two fixed SELECT-only tools over a checksummed, source-derived aggregate."""
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.db = duckdb.connect(':memory:')
        self.db.execute('SET threads=1')
        self.db.execute('CREATE TABLE retail(month VARCHAR, country VARCHAR, lines BIGINT, orders BIGINT, units BIGINT, gross_sales_gbp DECIMAL(24,6))')
        rows = [(r['month'],r['country'],r['lines'],r['orders'],r['units'],Decimal(r['gross_sales_gbp'])) for r in snapshot['monthly']]
        if rows:
            self.db.executemany('INSERT INTO retail VALUES (?, ?, ?, ?, ?, ?)', rows)
        self.db.execute('SET enable_external_access=false')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def _periods(self, before_month, after_month):
        if (before_month, after_month) != (BEFORE_MONTH, AFTER_MONTH):
            raise ToolError('Only complete October and November 2011 are supported')

    def _record(self, name, sql, result, start):
        return {'id':'ev_'+uuid.uuid4().hex[:10], 'tool':name,
                'args':{'before_month':BEFORE_MONTH,'after_month':AFTER_MONTH},
                'sql':sql, 'sql_parameters':[BEFORE_MONTH,AFTER_MONTH] * (2 if name == 'retail_country_contributions' else 1),
                'result':result, 'elapsed_ms':round((time.perf_counter()-start)*1000,2),
                'warnings':[], 'dataset_hash':self.snapshot['hash'], 'contract_version':'retail-1.0'}

    def compare_sales(self, before_month=BEFORE_MONTH, after_month=AFTER_MONTH):
        self._periods(before_month, after_month)
        start = time.perf_counter()
        sql = '''SELECT month, SUM(gross_sales_gbp), SUM(orders), SUM(lines), SUM(units)
FROM retail WHERE month IN (?, ?) GROUP BY month ORDER BY month'''
        rows = self.db.execute(sql,[before_month,after_month]).fetchall()
        if {r[0] for r in rows} != {before_month,after_month}:
            raise ToolError('Missing retail comparison month')
        values = {r[0]:{'gross_sales_gbp':float(r[1]), 'orders':r[2], 'lines':r[3], 'units':r[4]} for r in rows}
        before, after = values[before_month],values[after_month]
        delta = rows[1][1] - rows[0][1]
        return self._record('compare_retail_sales',sql,{'before':before,'after':after,'delta_gbp':float(delta),
                            'change_pct':float(delta/rows[0][1]*100) if rows[0][1] else None},start)

    def country_contributions(self, before_month=BEFORE_MONTH, after_month=AFTER_MONTH):
        self._periods(before_month, after_month)
        start = time.perf_counter()
        sql = '''SELECT country,
SUM(CASE WHEN month=? THEN gross_sales_gbp ELSE 0 END) AS before_gbp,
SUM(CASE WHEN month=? THEN gross_sales_gbp ELSE 0 END) AS after_gbp
FROM retail WHERE month IN (?, ?) GROUP BY country ORDER BY country'''
        rows = self.db.execute(sql,[before_month,after_month,before_month,after_month]).fetchall()
        countries = [{'country':r[0],'before_gbp':float(r[1]),'after_gbp':float(r[2]),'delta_gbp':float(r[2]-r[1])} for r in rows]
        return self._record('retail_country_contributions',sql,{'countries':countries,
                            'delta_gbp':float(sum((r[2]-r[1] for r in rows),Decimal(0)))},start)


def _unsupported(question):
    q = question.lower()
    if re.search(r'\b(activation|signup|funnel|experiment|retention|conversion|causal|profit|margin|products?|customers?|delete|drop|insert|update|shell|secret|password|today|yesterday|last|next|current|weekly|daily)\b|a/b|\bnet\s+(revenue|sales)\b|;',q):
        return True
    if any(year != '2011' for year in re.findall(r'\b(?:19|20)\d\d\b',q)):
        return True
    months = re.findall(r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',q)
    if any(month not in ('oct','october','nov','november') for month in months):
        return True
    dates = re.findall(r'\b20\d\d-\d\d(?:-\d\d)?\b',q)
    if any(value not in (BEFORE_MONTH,AFTER_MONTH) for value in dates):
        return True
    # This is deliberately a bounded vocabulary, not a general NL-to-SQL parser.
    # Unknown filters (country names, product IDs, other metrics) must not be
    # silently discarded while a fixed all-country comparison is presented.
    allowed = set('how did do does the gross positive sales revenue change changes changed increase increased decrease decreased from october oct to november nov compare which countries country contributed contribution contributions between and what data quality exclusions affect figures total totals in invoice invoices transaction transactions missing are have why a of for show me with versus vs by counts count number volume analyze investigate'.split())
    allowed.update(('2011','2011-10','2011-11'))
    if any(token not in allowed for token in re.findall(r'[a-z]+|\d+(?:-\d+)*',q)):
        return True
    if dates and set(dates) != {BEFORE_MONTH,AFTER_MONTH}:
        return True
    if dates and list(dict.fromkeys(dates)) != [BEFORE_MONTH,AFTER_MONTH]:
        return True
    if months and not ({'oct','october'} & set(months) and {'nov','november'} & set(months)):
        return True
    if months and list(dict.fromkeys(month[:3] for month in months)) != ['oct','nov']:
        return True
    if '2011' in re.findall(r'\b\d{4}\b',q) and not (months or dates):
        return True
    return not any(word in q for word in ('sales','revenue','country','countries','invoice','transaction','quality','missing','october','november'))


def run_retail_analysis(question: str, snapshot: dict | None = None) -> dict:
    begun = time.perf_counter()
    deadline = begun + REQUEST_TIMEOUT_SECONDS
    data = snapshot if snapshot is not None else load_snapshot()
    state = {'question':question,'mode':'deterministic','status':'running','summary':'',
             'evidence':[],'findings':[],'retrieval':[],'trace':[],
             'warnings':['Country contributions describe arithmetic change, not a causal explanation.',
                         'Gross positive sales exclude cancellations/nonpositive lines and are not net revenue or profit.',
                         'Transaction records contain no visits, SaaS activation, funnel events, or randomized assignments.',
                         'Exact duplicate rows are retained; missing customer identifiers do not exclude valid sales.'],
             'metrics':{'elapsed_ms':0,'tool_calls':0,'model_calls':0,'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0}}
    if not isinstance(question,str) or not 3 <= len(question) <= 1000 or _unsupported(question):
        state.update(status='unsupported',summary='This real-data case supports gross positive sales and country contributions for October versus November 2011 only. It cannot establish activation, funnels, A/B effects, net revenue or causality.')
    else:
        try:
            with RetailAnalytics(data) as tools:
                def guarded(fn):
                    def execute(s):
                        if time.perf_counter() >= deadline:
                            return {'status':'timed_out','summary':'Request deadline reached.','findings':[]}
                        result = fn(s)
                        if time.perf_counter() >= deadline:
                            result.update(status='timed_out',summary='Request deadline reached.',findings=[])
                        return result
                    return execute
                def retrieve(s):
                    return {'retrieval':retrieve_contracts(question),'trace':[{'step':'retrieve','detail':'Retrieved versioned public-retail metric and source contracts.'}]}
                def compare(s):
                    evidence = tools.compare_sales()
                    return {'evidence':[evidence],'metrics':{**s['metrics'],'tool_calls':1},
                            'trace':s['trace']+[{'step':'execute','detail':'Compared gross positive sales with parameterized SQL.'}]}
                def decompose(s):
                    evidence = tools.country_contributions()
                    return {'evidence':s['evidence']+[evidence],'metrics':{**s['metrics'],'tool_calls':2},
                            'trace':s['trace']+[{'step':'execute','detail':'Reconciled country contributions to the observed sales change.'}]}
                def report(s):
                    comparison = s['evidence'][0]; result = comparison['result']
                    if abs(result['delta_gbp']-s['evidence'][1]['result']['delta_gbp']) > 1e-6:
                        raise ToolError('Country contributions do not reconcile')
                    findings=[]
                    for label,path in [('October gross positive sales','before.gross_sales_gbp'),('November gross positive sales','after.gross_sales_gbp'),('Sales change','delta_gbp')]:
                        value=result
                        for key in path.split('.'): value=value[key]
                        findings.append({'label':label,'field_path':path,'value':value,'unit':'GBP','scale':1,'evidence_id':comparison['id']})
                    validate_findings(findings,s['evidence'])
                    return {'status':'completed','findings':findings,
                            'summary':f"Gross positive sales changed from £{result['before']['gross_sales_gbp']:,.2f} in October 2011 to £{result['after']['gross_sales_gbp']:,.2f} in November 2011, a change of £{result['delta_gbp']:+,.2f}. Country contributions reconcile to this total; the records do not establish why demand changed.",
                            'trace':s['trace']+[{'step':'verify','detail':'Checked numerical findings against SQL evidence and country totals.'}]}
                graph=StateGraph(State)
                for name,fn in [('retrieve',retrieve),('compare',compare),('decompose',decompose),('report',report)]:graph.add_node(name,guarded(fn))
                graph.add_edge(START,'retrieve')
                for source,target in [('retrieve','compare'),('compare','decompose'),('decompose','report')]:
                    graph.add_conditional_edges(source,lambda s,target=target:target if s['status']=='running' else END)
                graph.add_edge('report',END)
                state=dict(graph.compile().invoke(state,{'recursion_limit':8}))
        except Exception:
            state.update(status='invalid_data',summary='The public-data investigation failed; no verified report is available.',findings=[])
    elapsed=time.perf_counter()-begun
    if state['status']=='completed' and elapsed>=REQUEST_TIMEOUT_SECONDS:
        state.update(status='timed_out',summary='Request deadline reached.',findings=[])
    state['metrics']['elapsed_ms']=round(elapsed*1000,2)
    return {**state,'request_id':uuid.uuid4().hex,'model':None,
            'dataset':{'hash':data['hash'],'label':data['source']['name'],'source_type':'real_public_transactions',
                       'source_rows':data['source']['source_rows'],'source':data['source'],'audit':data['audit'],
                       'before_month':BEFORE_MONTH,'after_month':AFTER_MONTH}}
