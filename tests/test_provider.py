"""Offline transport/accounting tests; a dummy key is never transmitted externally."""
import pytest
import httpx
from backend import provider
from backend.budget import BudgetError

@pytest.fixture
def state(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-placeholder-not-a-real-key')
    return {'question':'Explain activation','retrieval':[],'evidence':[],
            'metrics':{'model_calls':0,'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0}}

def test_failed_provider_attempt_retains_conservative_charge(state,monkeypatch):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k: (_ for _ in ()).throw(httpx.ReadTimeout('mock')))
    with pytest.raises(ValueError,match='Provider request failed'): provider.choose_action(state)
    assert state['metrics']['model_calls']==1
    assert state['metrics']['estimated_cost_usd']>0
    assert state['metrics']['uncertain_usage_calls']==1

def test_missing_usage_is_not_reported_as_free(state,monkeypatch):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"action":"finish","segment":"acquisition_channel","experiment_id":"onboarding_valid","reason":"done"}'}}]}))
    provider.choose_action(state)
    assert state['metrics']['estimated_cost_usd']>0
    assert state['metrics']['uncertain_usage_calls']==1

def test_no_network_when_per_request_cap_would_be_exceeded(state,monkeypatch):
    state['metrics']['estimated_cost_usd']=.0149
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:pytest.fail('network must not run'))
    with pytest.raises(BudgetError): provider.choose_action(state)
    assert state['metrics']['model_calls']==0

def test_provider_usage_is_charged_once_before_parsing_failure(state,monkeypatch):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':50},'choices':[{'finish_reason':'stop','message':{'content':'bad json'}}]}))
    with pytest.raises(ValueError): provider.choose_action(state)
    assert state['metrics']['model_calls']==1
    assert state['metrics']['input_tokens']==100
    assert state['metrics']['estimated_cost_usd']==pytest.approx(.00012)

def test_standard_service_tier_is_explicit(state,monkeypatch):
    def post(*args,**kwargs):
        assert kwargs['json']['service_tier']=='default'
        return httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':'{"action":"finish","segment":"acquisition_channel","experiment_id":"onboarding_valid","reason":"done"}'}}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    provider.choose_action(state)

@pytest.mark.parametrize('status',[401,403,429,503])
def test_provider_http_failure_exposes_only_safe_status(state,monkeypatch,status):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:httpx.Response(status,text='secret-shaped provider body must never appear'))
    with pytest.raises(ValueError): provider.choose_action(state)
    assert state['metrics']['last_provider_http_status']==status
    assert state['metrics']['last_provider_error']=='http_error'
    assert 'secret-shaped' not in str(state)

def test_transport_failure_has_safe_error_category(state,monkeypatch):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k: (_ for _ in ()).throw(httpx.ConnectError('private transport payload')))
    with pytest.raises(ValueError): provider.choose_action(state)
    assert state['metrics']['last_provider_error']=='ConnectError'
    assert 'private transport' not in str(state)

def test_missing_transport_dependency_fails_without_secret_output(state,monkeypatch):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k: (_ for _ in ()).throw(ImportError('private configuration detail')))
    with pytest.raises(ValueError,match='Provider transport configuration failed'): provider.choose_action(state)
    assert state['metrics']['last_provider_error']=='transport_configuration'
    assert 'private configuration' not in str(state)

def test_completed_tool_is_removed_from_next_action_schema(state,monkeypatch):
    state['evidence']=[{'id':'ev_done','tool':'analyze_funnel','args':{},'result':{'before':{},'after':{}},'warnings':[]}]
    def post(*args,**kwargs):
        allowed=kwargs['json']['response_format']['json_schema']['schema']['properties']['action']['enum']
        assert 'analyze_funnel' not in allowed
        assert 'finish' in allowed
        return httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':'{"action":"finish","segment":"acquisition_channel","experiment_id":"onboarding_valid","reason":"done"}'}}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    assert provider.choose_action(state)[0]['action']=='finish'

def test_provider_timeout_is_bounded_by_remaining_request_deadline(state,monkeypatch):
    state['started']=10.0
    monkeypatch.setattr(provider.time,'perf_counter',lambda:54.5)
    def post(*args,**kwargs):
        assert kwargs['timeout']==.5
        return httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':'{"action":"finish","segment":"acquisition_channel","experiment_id":"onboarding_valid","reason":"done"}'}}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    provider.choose_action(state)

def test_answer_schema_constrains_numbers_and_derives_fact_ids(state,monkeypatch):
    import re
    state['evidence']=[{'id':'ev_real','tool':'compare_metric','args':{},'sql':'SELECT approved','result':{'delta_pp':-12.5},'warnings':[]}]
    state['retrieval']=[{'id':'activation','title':'Activation','text':'Definition'}]
    facts=[{'id':'f0','label':'Change','value':-12.5,'unit':'pp','evidence_id':'ev_real','field_path':'delta_pp','scale':1}]
    def post(*args,**kwargs):
        schema=kwargs['json']['response_format']['json_schema']['schema']
        properties=schema['properties']['claims']['items']['properties']
        assert properties['fact_ids']['items']['enum']==['f0']
        pattern=properties['text']['pattern']
        assert re.fullmatch(pattern,'Activation declined between the documented cohorts.')
        assert not re.fullmatch(pattern,'The change is {{f0}}.')
        assert not re.fullmatch(pattern,'The change is 12.5.')
        assert not re.fullmatch(pattern,'The change is {{f999}}.')
        assert properties['evidence_ids']['items']['enum']==['ev_real']
        assert properties['contract_ids']['items']['enum']==['activation']
        answer={'status':'answered','abstention_reason':'','claims':[{'text':'Activation declined between the documented cohorts.','fact_ids':['f0'],'evidence_ids':['ev_real'],'contract_ids':['activation']}]}
        import json
        return httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    answer,_=provider.generate_answer(state,facts)
    assert answer['claims'][0]['fact_ids']==['f0']

@pytest.mark.parametrize('tool,arg,first,second',[('decompose_change','segment','acquisition_channel','signup_device'),('check_experiment','experiment_id','onboarding_valid','onboarding_srm')])
def test_distinct_argument_combination_remains_available(state,monkeypatch,tool,arg,first,second):
    state['evidence']=[{'id':'ev_done','tool':tool,'args':{arg:first},'result':{},'warnings':[]}]
    def post(*args,**kwargs):
        allowed=kwargs['json']['response_format']['json_schema']['schema']['properties']['action']['enum']
        assert tool in allowed
        return httpx.Response(200,json={'usage':{'prompt_tokens':100,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':'{"action":"finish","segment":"acquisition_channel","experiment_id":"onboarding_valid","reason":"done"}'}}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    provider.choose_action(state)
