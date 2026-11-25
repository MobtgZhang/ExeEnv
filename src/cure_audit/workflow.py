"""CURE's four-stage algorithm using caller-supplied completion and observation.

This module has no networking, credential handling, service configuration, or
default generator. Replaying saved observations does not execute generated code.
"""
import json
from .scoring import public_task, should_route


def parse_outer(text):
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == '{':
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
    return {}


def prompt_observation(value):
    if isinstance(value, list):
        return [prompt_observation(v) for v in value]
    return {k: v for k, v in value.items() if k != 'seconds'}


def run(task, complete, observe, prompts, policy='original'):
    """Run on public input only; caller scores the returned answer afterwards.

    complete(stage, messages, requested_limit, temperature) returns a parsed
    JSON object. observe(stage, parsed) returns a saved/isolated observation.
    Fallback applies only to downstream failure after a nonempty draft; an
    explicitly empty final answer retains its historical zero-score behavior.
    """
    if policy not in {'original', 'agreement', 'fallback', 'both'}:
        raise ValueError('Unknown policy')
    public = public_task(task)
    messages = [dict(role='system', content=prompts['SYSTEM'] + prompts['FORMAT']),
                dict(role='user', content=json.dumps(public, ensure_ascii=False))]
    draft = {}
    try:
        draft = complete('draft', messages, 1536, 0)
        ledger = complete('ledger', messages + [dict(role='user', content=prompts['LEDGER'])], 1536, 0)
        ledger_obs = observe('ledger', ledger)
        stage_input = json.dumps(dict(ledger=ledger, observation=prompt_observation(ledger_obs)), ensure_ascii=False)
        checker = complete('independent_solution', messages + [dict(role='user', content=prompts['CHALLENGE'] + '\n' + stage_input)], 1536, 0)
        checker_obs = observe('independent_solution', checker)
        if policy in {'agreement', 'both'} and should_route(dict(public, benchmark=task['benchmark']), draft, checker):
            return dict(status='scored', prediction=str(draft['final_answer']).strip(), branch='agreement')
        pack = dict(draft=draft, ledger=ledger, independent=checker,
                    observations=prompt_observation([ledger_obs, checker_obs]))
        final = complete('final_answer', messages + [dict(role='user', content=prompts['FINAL'] + '\n' + json.dumps(pack, ensure_ascii=False))], 1536, 0)
        return dict(status='scored', prediction=str(final.get('final_answer') or '').strip(), branch='original')
    except (RuntimeError, ValueError) as exc:
        answer = str(draft.get('final_answer') or '').strip()
        if answer and policy in {'fallback', 'both'}:
            return dict(status='scored', prediction=answer, branch='fallback')
        return dict(status='unavailable', prediction='', branch='unavailable', failure_type=type(exc).__name__)
