"""LLM synthesis from retrieved contracts and computed facts; fail closed on grounding.

Numeric substitution and citation resolution are checked mechanically. This is not a
semantic entailment proof: qualitative statements still require benchmark review.
"""
from __future__ import annotations

import math
import re

from .provider import MODEL, ANSWER_SCHEMA_VERSION, account_usage, generate_answer


class GroundingError(ValueError):
    pass


def resolve_field(value, path):
    try:
        for key in path.split('.'):
            value = value[int(key)] if isinstance(value, list) and key.isdecimal() else value[key]
        return value
    except (KeyError, IndexError, TypeError, ValueError):
        raise GroundingError('Unresolved evidence field') from None


def fact_catalog(findings):
    """Stable request-local IDs; the model references these, never supplies numbers."""
    return [{**finding, 'id':f'f{index}'} for index,finding in enumerate(findings)]


def _validated_facts(findings, evidence):
    facts = fact_catalog(findings)
    for fact in facts:
        if fact['evidence_id'] not in evidence:
            raise GroundingError('Unresolved evidence reference')
        expected = resolve_field(evidence[fact['evidence_id']]['result'],fact['field_path'])
        actual, scale = fact['value'], fact['scale']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (actual,expected,scale)):
            raise GroundingError('Invalid numeric finding')
        if abs(actual-expected*scale)>1e-9:
            raise GroundingError('Report value does not match evidence')
    return {fact['id']:fact for fact in facts}


def _render_fact(fact):
    # The exact machine value remains alongside the display, including tiny p-values.
    value = format(fact['value'],'.8g') if fact['unit']=='p' else format(fact['value'],',.4f').rstrip('0').rstrip('.')
    return f"{value} {fact.get('unit','')}".strip()


def validate_answer(answer, state, findings):
    evidence={item['id']:item for item in state['evidence']}
    contracts={item['id']:item for item in state['retrieval']}
    facts=_validated_facts(findings,evidence)
    metadata={'method':'llm_grounded','schema_version':ANSWER_SCHEMA_VERSION,'model':MODEL,'numeric_validation':'passed',
              'citation_validation':'passed','numeric_validation_scope':'Server-rendered fact values and explicit quantity checks; narrative entailment needs review.','semantic_validation':'not_automated'}
    if not isinstance(answer,dict) or set(answer)!={'status','claims','abstention_reason'}:
        raise GroundingError('Invalid answer schema')
    if answer['status']=='abstained':
        if answer['claims'] or answer['abstention_reason'] not in ('insufficient_evidence','conflicting_evidence','unsupported_question'):
            raise GroundingError('Invalid abstention')
        return {'status':'abstained','summary':'The model abstained because the available evidence did not support a reliable answer.',
                'findings':[],'claims':[],'citations':[],'generation':metadata}
    if answer['status']!='answered' or answer['abstention_reason']!='' or not isinstance(answer['claims'],list) or not 1<=len(answer['claims'])<=6:
        raise GroundingError('No supported generated claims')
    invalid_experiment=any(e['tool']=='check_experiment' and e['result'].get('status')=='invalid' for e in evidence.values())
    rendered=[]; citations={}; used_facts=set(); used_contracts=set()
    for claim in answer['claims']:
        if not isinstance(claim,dict) or set(claim)!={'text','fact_ids','evidence_ids','contract_ids'}:
            raise GroundingError('Invalid claim schema')
        text=claim['text']
        if not isinstance(text,str) or not 1<=len(text)<=1200:
            raise GroundingError('Invalid claim text')
        for key in ('fact_ids','evidence_ids','contract_ids'):
            if not isinstance(claim[key],list) or any(not isinstance(v,str) for v in claim[key]):
                raise GroundingError('Invalid citation list')
        if not claim['evidence_ids'] and not claim['contract_ids']:
            raise GroundingError('Uncited generated claim')
        if any(key not in evidence for key in claim['evidence_ids']) or any(key not in contracts for key in claim['contract_ids']):
            raise GroundingError('Unresolved citation')
        placeholders=re.findall(r'\{\{(f\d+)\}\}',text)
        if (placeholders and set(placeholders)!=set(claim['fact_ids'])) or any(key not in facts for key in claim['fact_ids']):
            raise GroundingError('Unresolved or unused numeric fact')
        # A placeholder is a complete signed quantity with its unit, not an
        # arithmetic operand. Prefixing '-' or '(...)' could reverse its meaning.
        for match in re.finditer(r'\{\{f\d+\}\}',text):
            before, after = text[:match.start()].rstrip(), text[match.end():].lstrip()
            if (before and before[-1] in '+-−–—*/^=<>×÷($£€%') or (after and after[0] in '+-−–—*/^=<>×÷)%'):
                raise GroundingError('Numeric placeholders cannot have sign, arithmetic, currency or percentage modifiers')
            if re.search(r'\b(minus|plus|negative|positive|negated|times)\s*$',before,re.I):
                raise GroundingError('Numeric placeholders cannot have worded sign modifiers')
        plain=re.sub(r'\{\{f\d+\}\}','',text)
        if re.search(r'\d|[{}]|https?://|\[|\]',plain):
            raise GroundingError('Unverified literal number, placeholder, or external citation')
        quantity_text=plain
        if any(isinstance(e.get('result'),dict) and {'before','after'} <= e['result'].keys() for e in evidence.values()):
            quantity_text=re.sub(r'\btwo (?:(?:consecutive|documented) )?(?:signup )?(?:cohorts|months|periods)\b','the compared cohorts',quantity_text,flags=re.I)
        if any('seven' in doc.get('text','').lower() for doc in contracts.values()):
            quantity_text=re.sub(r'\bseven(?:-day| days?)\b','the documented window',quantity_text,flags=re.I)
        for source_id in claim['evidence_ids']:
            selected={facts[key]['field_path']:facts[key]['value'] for key in claim['fact_ids'] if key in facts and facts[key]['evidence_id']==source_id}
            if {'ci_low_pp','ci_high_pp'} <= selected.keys() and 'interval' in plain.lower():
                contains_null=selected['ci_low_pp'] <= 0 <= selected['ci_high_pp']
                negative_phrase=r"\b(?:does not|doesn't) (?:include|contain|cross|cover) zero\b|\bexcludes? zero\b"
                positive_phrase=r'\b(?:includes?|contains?|crosses|covers) zero\b'
                if re.search(negative_phrase,quantity_text,re.I):
                    if contains_null:
                        raise GroundingError('Interval narrative contradicts the selected bounds')
                    quantity_text=re.sub(negative_phrase,'excludes the null effect',quantity_text,flags=re.I)
                elif re.search(positive_phrase,quantity_text,re.I):
                    if not contains_null:
                        raise GroundingError('Interval narrative contradicts the selected bounds')
                    quantity_text=re.sub(positive_phrase,'includes the null effect',quantity_text,flags=re.I)
        if not placeholders and (not plain.isascii() or re.search(r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fourty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|half|halves|halved|quarter|dozen|twice|thrice|doubl(?:e[sd]?|ing)|tripl(?:e[sd]?|ing)|quadrupl(?:e[sd]?|ing)|[a-z]*fold)\b',quantity_text,re.I)):
            raise GroundingError('Qualitative text cannot contain worded quantities or non-ASCII numeric obfuscation')
        # Explicitly reject common causal/rollout overclaims. Not an entailment judge.
        if re.search(r'\b(caused|causes|proved|proves|guarantees)\b|\b(should|must)\s+(ship|roll\s*out|deploy)\b',plain,re.I):
            raise GroundingError('Unsupported causal or rollout claim')
        significance_text=plain
        supported_srm=('srm' in claim['contract_ids'] and any(
            facts[key]['field_path']=='srm_pvalue' and facts[key]['scale']==1 and facts[key]['unit']=='p'
            and 0 <= facts[key]['value'] < .001
            and facts[key]['evidence_id'] in claim['evidence_ids']
            and evidence[facts[key]['evidence_id']]['tool']=='check_experiment'
            and evidence[facts[key]['evidence_id']]['result'].get('status')=='invalid'
            for key in claim['fact_ids']))
        if supported_srm:
            # Significance of the actual SRM allocation test is supported. This
            # does not grant permission to interpret an experiment's effect.
            for pattern in (
                r'\b(?:statistically )?significant (?:(?:assignment|allocation) imbalance|sample ratio mismatch)\b',
                r'\b(?:(?:assignment|allocation) imbalance|sample ratio mismatch) (?:is|was) (?:statistically )?significant\b',
            ):
                for match in re.finditer(pattern,significance_text,re.I):
                    if re.search(r"\b(?:no|not|non|never|without|absence|cannot|lack(?:s|ing)?|[a-z]+n't)\b",plain,re.I):
                        raise GroundingError('SRM narrative contradicts the selected allocation test')
                significance_text=re.sub(pattern,'verified SRM allocation finding',significance_text,flags=re.I)
        if re.search(r'\bsignificant(?:ly)?\b|\bvalid randomization\b|\bensur(?:e[sd]?|ing)\b.{0,40}\bcomparab',significance_text,re.I):
            raise GroundingError('Unsupported significance or cohort-comparability claim')
        if invalid_experiment and re.search(r'\b(beneficial|significant|positive|negative)\s+(effect|lift|uplift)|\btreatment\s+(produced|improved|increased)',plain,re.I):
            raise GroundingError('Invalid experiment cannot support an effect conclusion')
        blocks=[]
        for key in claim['fact_ids']:
            fact=facts[key]
            if fact['evidence_id'] not in claim['evidence_ids']:
                raise GroundingError('Numeric claim lacks its evidence citation')
            if placeholders:
                text=text.replace('{{'+key+'}}',_render_fact(fact))
            else:
                label=re.sub(r'\d+(?:\.\d+)?%?','',fact['label']).strip()
                blocks.append(label+': '+_render_fact(fact))
            used_facts.add(key)
        if blocks:
            text=text.rstrip()+' '+ '; '.join(blocks)+'.'
        for key in claim['evidence_ids']:
            citations[key]={'id':key,'kind':'evidence','title':evidence[key]['tool']}
        for key in claim['contract_ids']:
            citations[key]={'id':key,'kind':'contract','title':contracts[key]['title']}
            used_contracts.add(key)
        rendered.append({**claim,'text':text})
    if not used_contracts or not used_facts:
        raise GroundingError('A grounded answer must cite retrieved definitions and computed facts')
    return {'status':'invalid_data' if invalid_experiment else 'completed',
            'summary':' '.join(claim['text'] for claim in rendered),'claims':rendered,
            'citations':list(citations.values()),'findings':findings,'generation':metadata}


def generate_report(state, findings):
    """Generate once. Rejected prose never leaks into the user report; usage remains."""
    metrics=state['metrics']
    try:
        answer,usage=generate_answer(state,fact_catalog(findings))
        account_usage(metrics,usage)
        result=validate_answer(answer,state,findings)
    except GroundingError as exc:
        result={'status':'verification_failed','summary':'The generated answer failed grounding checks; no unverified narrative is shown.',
                'findings':[],'claims':[],'citations':[],
                'generation':{'method':'llm_grounded','schema_version':ANSWER_SCHEMA_VERSION,'model':MODEL,'numeric_validation':'failed','citation_validation':'failed','semantic_validation':'not_automated','validation_failure_reason':str(exc)}}
    return {**result,'metrics':metrics,'warnings':state.get('warnings',[]),
            'trace':state.get('trace',[])+[{'step':'generate','detail':'Generated an answer using retrieved definitions and actual SQL evidence.'},
                                        {'step':'verify','detail':'Checked numeric substitutions and citation targets. Qualitative entailment requires separate review.'}]}
