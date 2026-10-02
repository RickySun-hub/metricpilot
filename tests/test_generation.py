"""Grounded-answer safety tests. All provider output is mocked; no paid calls."""
from copy import deepcopy
import math
import pytest
from backend import generation

@pytest.fixture
def grounded():
    state = {'question':'Explain activation change', 'evidence':[{'id':'ev_real','tool':'compare_metric','result':{'delta_pp':-12.5},'sql':'SELECT approved_metric','warnings':[]}],
             'retrieval':[{'id':'mix_shift','title':'Mix decomposition','text':'The decomposition is descriptive, not causal.','version':'1.0'}],
             'metrics':{'model_calls':0,'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0},'trace':[], 'warnings':[]}
    findings = [{'label':'Activation change','value':-12.5,'unit':'pp','evidence_id':'ev_real','field_path':'delta_pp','scale':1}]
    answer = {'status':'answered','abstention_reason':'','claims':[{'text':'The activation change is {{f0}}; this is descriptive, not causal.','fact_ids':['f0'],'evidence_ids':['ev_real'],'contract_ids':['mix_shift']}]}
    return state, findings, answer

def test_grounded_answer_renders_only_verified_values_and_citations(grounded):
    state, findings, answer = grounded
    result = generation.validate_answer(answer,state,findings)
    assert '-12.5 pp' in result['summary']
    assert {c['id'] for c in result['citations']} == {'ev_real','mix_shift'}
    assert result['claims'][0]['fact_ids'] == ['f0']
    assert result['generation']['semantic_validation'] == 'not_automated'

@pytest.mark.parametrize('tamper', ['invented_evidence','invented_contract','invented_fact','uncited_fact','raw_number','empty_claims','no_contract','nonfinite','changed_value','unknown_placeholder','causal_claim','invalid_effect'])
def test_unverifiable_answer_is_rejected(grounded,tamper):
    state, findings, answer = deepcopy(grounded)
    claim=answer['claims'][0]
    if tamper=='invented_evidence': claim['evidence_ids']=['ev_fake']
    elif tamper=='invented_contract': claim['contract_ids']=['missing']
    elif tamper=='invented_fact': claim['fact_ids']=['f999']
    elif tamper=='uncited_fact': claim['evidence_ids']=[]
    elif tamper=='raw_number': claim['text']='Activation changed by 999 percent.'
    elif tamper=='empty_claims': answer['claims']=[]
    elif tamper=='no_contract': claim['contract_ids']=[]
    elif tamper=='nonfinite': findings[0]['value']=math.nan
    elif tamper=='changed_value': findings[0]['value']=12.5
    elif tamper=='unknown_placeholder': claim['text']='The result is {{f999}}.'
    elif tamper=='causal_claim': claim['text']='The channel mix caused the activation decline of {{f0}}.'
    elif tamper=='invalid_effect': state['evidence'][0]['tool']='check_experiment'; state['evidence'][0]['result']['status']='invalid'; claim['text']='Treatment produced a beneficial effect of {{f0}}.'
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)

def test_explicit_abstention_has_no_generated_claims(grounded):
    state,findings,answer=grounded
    answer.update(status='abstained',claims=[],abstention_reason='insufficient_evidence')
    result=generation.validate_answer(answer,state,findings)
    assert result['status']=='abstained'
    assert result['findings']==[]
    assert result['claims']==[]

def test_generation_failure_preserves_usage_and_abstains(grounded,monkeypatch):
    state,findings,answer=grounded
    answer['claims'][0]['text']='The change is 400 percent.'
    monkeypatch.setattr(generation,'generate_answer',lambda s,f:(answer,{'prompt_tokens':100,'completion_tokens':50}))
    result=generation.generate_report(state,findings)
    assert result['status']=='verification_failed'
    assert result['findings']==[]
    assert result['metrics']['model_calls']==1
    assert result['metrics']['input_tokens']==100
    assert result['metrics']['estimated_cost_usd']>0
    assert '400' not in result['summary']

def test_successful_generation_is_not_a_template(grounded,monkeypatch):
    state,findings,answer=grounded
    monkeypatch.setattr(generation,'generate_answer',lambda s,f:(answer,{}))
    result=generation.generate_report(state,findings)
    assert result['status']=='completed'
    assert result['generation']['method']=='llm_grounded'
    assert result['summary'].startswith('The activation change is')

def test_lists_are_valid_evidence_paths(grounded):
    state,findings,answer=grounded
    state['evidence'][0]['result']={'countries':[{'delta_gbp':-12.5}]}
    findings[0]['field_path']='countries.0.delta_gbp'
    assert generation.validate_answer(answer,state,findings)['status']=='completed'

def test_live_graph_invokes_actual_generation_stage(monkeypatch):
    from backend import agent
    from backend.data import generate_dataset
    monkeypatch.setattr(agent,'live_available',lambda:True)
    monkeypatch.setattr(agent,'reserve',lambda **k:None)
    def choose(state):
        action='compare_metric' if not state['evidence'] else 'finish'
        return {'action':action,'segment':'acquisition_channel','experiment_id':'onboarding_valid','reason':'offline mock'},{}
    monkeypatch.setattr(agent,'choose_action',choose)
    def generate(state,facts):
        return {'status':'answered','abstention_reason':'','claims':[{'text':'Earlier activation was {{f0}} and later activation was {{f1}}.',
          'fact_ids':['f0','f1'],'evidence_ids':[facts[0]['evidence_id']],'contract_ids':[state['retrieval'][0]['id']]}]},{}
    monkeypatch.setattr(generation,'generate_answer',generate)
    report=agent.run_analysis('Compare activation',mode='live',dataset=generate_dataset(users=100))
    assert report['status']=='completed'
    assert report['generation']['method']=='llm_grounded'
    assert report['metrics']['model_calls']==3
    assert report['citations'] and report['claims']

def test_late_generation_cannot_return_verified_claims(monkeypatch):
    from backend import agent
    from backend.data import generate_dataset
    clock={'now':0.}
    monkeypatch.setattr(agent,'live_available',lambda:True)
    monkeypatch.setattr(agent,'reserve',lambda **k:None)
    monkeypatch.setattr(agent.time,'perf_counter',lambda:clock['now'])
    monkeypatch.setattr(agent,'choose_action',lambda state:({'action':'compare_metric' if not state['evidence'] else 'finish','segment':'acquisition_channel','experiment_id':'onboarding_valid','reason':'mock'},{}))
    def generate(state,findings):
        clock['now']=46
        return {'status':'completed','summary':'late text','findings':findings,'claims':[{'text':'late'}],'citations':[{'id':'late'}],'metrics':state['metrics']}
    monkeypatch.setattr(agent,'generate_report',generate)
    report=agent.run_analysis('Compare activation',mode='live',dataset=generate_dataset(users=100))
    assert report['status']=='timed_out'
    assert not report['findings'] and not report['claims'] and not report['citations']

def test_funnel_catalog_exposes_conditional_completion_and_counts():
    from backend.agent import _findings
    from backend.data import generate_dataset
    from backend.tools import Analytics
    engine=Analytics(generate_dataset(users=100))
    try:
        evidence=engine.analyze_funnel()
        findings=_findings([evidence])
        by_path={item['field_path']:item for item in findings}
        for period in ('before','after'):
            for field in ('users','started','completed','conditional_completion_rate'):
                assert f'{period}.{field}' in by_path
        assert by_path['before.conditional_completion_rate']['scale']==100
    finally:
        engine.close()

@pytest.mark.parametrize('template', ['The change is -{{f0}}.', 'The change is −{{f0}}.', 'The change is + {{f0}}.',
                                     'The change is {{f0}}%.', 'The change is ({{f0}}).',
                                     'The change is minus {{f0}}.', 'The change is negative {{f0}}.'])
def test_numeric_placeholder_cannot_be_modified(grounded,template):
    state,findings,answer=grounded
    findings[0]['value']=12.5
    state['evidence'][0]['result']['delta_pp']=12.5
    answer['claims'][0]['text']=template
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)

def test_rejected_model_prose_cannot_leak_via_action_trace(monkeypatch):
    from backend import agent
    from backend.data import generate_dataset
    monkeypatch.setattr(agent,'live_available',lambda:True)
    monkeypatch.setattr(agent,'reserve',lambda **k:None)
    monkeypatch.setattr(agent,'choose_action',lambda state:({'action':'compare_metric' if not state['evidence'] else 'finish','segment':'acquisition_channel','experiment_id':'onboarding_valid','reason':'Activation improved by 9999 percent. Treatment caused the uplift; ship it.'},{}))
    monkeypatch.setattr(generation,'generate_answer',lambda *args:({'status':'answered','abstention_reason':'','claims':[]},{}))
    report=agent.run_analysis('Compare activation',mode='live',dataset=generate_dataset(users=100))
    assert report['status']=='verification_failed'
    assert '9999' not in str(report['trace'])
    assert 'ship it' not in str(report)

@pytest.mark.parametrize('text',['Activation decreased significantly by {{f0}}.',
                                 'Equal sample sizes ensure comparability at {{f0}}.',
                                 'The cohorts have {{f0}}, ensuring comparability.'])
def test_statistical_and_comparability_overclaims_are_withheld(grounded,text):
    state,findings,answer=grounded
    answer['claims'][0]['text']=text
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)

def test_fact_blocks_render_selected_values_without_model_numeric_prose(grounded):
    state,findings,answer=grounded
    answer['claims'][0]['text']='Activation declined across the documented cohorts.'
    result=generation.validate_answer(answer,state,findings)
    assert result['claims'][0]['text']=='Activation declined across the documented cohorts. Activation change: -12.5 pp.'


def test_contextual_two_cohorts_requires_before_after_evidence(grounded):
    state,findings,answer=grounded
    answer['claims'][0]['text']='Activation declined between the two consecutive signup cohorts.'
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)
    state['evidence'][0]['result'].update(before={},after={})
    assert generation.validate_answer(answer,state,findings)['status']=='completed'


@pytest.mark.parametrize('text',['Activation fell by thirty percent.','Activation fell by one hundred percent.','Activation is one million users.'])
def test_fact_block_prose_cannot_hide_worded_measurements(grounded,text):
    state,findings,answer=grounded
    answer['claims'][0]['text']=text
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)

@pytest.mark.parametrize('text',['Activation doubled.','Half of users activated.','Activation fell by a dozen percentage points.','Activation fell to a quarter of its prior level.','Activation increased tenfold.'])
def test_qualitative_claim_rejects_implicit_quantities(grounded,text):
    state,findings,answer=grounded
    answer['claims'][0]['text']=text
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)


@pytest.mark.parametrize('text',['The confidence interval includes zero.','The confidence interval crosses zero.'])
def test_zero_interval_phrase_requires_selected_bounds(grounded,text):
    state,findings,answer=grounded
    answer['claims'][0]['text']=text
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)
    state['evidence'][0]['result'].update(ci_low_pp=-2,ci_high_pp=3)
    findings += [{**findings[0],'label':'Lower bound','field_path':'ci_low_pp','value':-2},{**findings[0],'label':'Upper bound','field_path':'ci_high_pp','value':3}]
    answer['claims'][0]['fact_ids']=['f1','f2']
    assert generation.validate_answer(answer,state,findings)['status']=='completed'
    state['evidence'][0]['result']['ci_low_pp']=2
    findings[1]['value']=2
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,findings)

@pytest.fixture
def srm_grounded():
    state={'question':'Check the experiment','evidence':[{'id':'ev_srm','tool':'check_experiment','result':{'status':'invalid','srm_pvalue':1e-8},'warnings':[]}],
           'retrieval':[{'id':'srm','title':'Sample ratio mismatch','text':'p below 0.001 blocks interpretation.'}], 'metrics':{},'trace':[]}
    facts=[{'label':'SRM p-value','value':1e-8,'unit':'p','evidence_id':'ev_srm','field_path':'srm_pvalue','scale':1}]
    answer={'status':'answered','abstention_reason':'','claims':[{'text':'The experiment failed the sample ratio mismatch check, indicating a significant assignment imbalance.','fact_ids':['f0'],'evidence_ids':['ev_srm'],'contract_ids':['srm']}]}
    return state,facts,answer


def test_actual_srm_test_supports_assignment_significance(srm_grounded):
    state,facts,answer=srm_grounded
    assert generation.validate_answer(answer,state,facts)['status']=='invalid_data'


@pytest.mark.parametrize('change',['large_p','missing_fact','missing_contract','wrong_tool','valid_status','effect_claim','mixed_effect_claim'])
def test_srm_significance_exception_cannot_authorize_effect_claims(srm_grounded,change):
    state,facts,answer=srm_grounded
    if change=='large_p': state['evidence'][0]['result']['srm_pvalue']=facts[0]['value']=.1
    elif change=='missing_fact': answer['claims'][0]['fact_ids']=[]
    elif change=='missing_contract': answer['claims'][0]['contract_ids']=[]
    elif change=='wrong_tool': state['evidence'][0]['tool']='compare_metric'
    elif change=='valid_status': state['evidence'][0]['result']['status']='valid'
    elif change=='effect_claim': answer['claims'][0]['text']='The experiment shows a significant treatment effect.'
    elif change=='mixed_effect_claim': answer['claims'][0]['text']+=' The treatment effect is significant.'
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,facts)

@pytest.mark.parametrize('text',['There is no significant assignment imbalance.','There is not a statistically significant sample ratio mismatch.','The experiment did not show a significant allocation imbalance.','The experiment has no statistically significant sample ratio mismatch.','A significant assignment imbalance was not found.'])
def test_srm_significance_cannot_be_negated_against_evidence(srm_grounded,text):
    state,facts,answer=srm_grounded
    answer['claims'][0]['text']=text
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,facts)


def test_srm_significance_uses_unscaled_probability(srm_grounded):
    state,facts,answer=srm_grounded
    state['evidence'][0]['result']['srm_pvalue']=.1
    facts[0].update(scale=1e-6,value=1e-7)
    with pytest.raises(generation.GroundingError): generation.validate_answer(answer,state,facts)
