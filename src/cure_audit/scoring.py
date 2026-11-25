"""Frozen reference scorer and answer-only routing; no inference or configuration."""
import re

def public_task(task):
    """Explicit whitelist: answer/evaluation/trajectories never enter a prompt."""
    result = {k: task[k] for k in ['question', 'options', 'subtask'] if k in task}
    context = task.get('context') or {}
    result['evidence'] = {k: context[k] for k in ['protocol', 'key_passage', 'paper_title', 'source', 'tool_trace', 'web_evidence'] if context.get(k)}
    return result

def normalize_gaia(text):
    text=str(text).strip()
    try:
        return ('number',float(text.replace(',','').replace('$','').replace('%','')))
    except ValueError:
        pass
    def norm(v):
        return re.sub(r'[^\w]','',v).lower().replace('_','')
    if ',' in text or ';' in text:
        return ('list',tuple(sorted(norm(v) for v in re.split('[,;]',text))))
    return ('text',norm(text))

def score(task, answer):
    if task['benchmark']=='lab_bench':
        letter=re.fullmatch(r'\(?([A-Za-z])\)?[.)]?',answer.strip())
        if letter:
            idx=ord(letter.group(1).upper())-65
            answer=task['options'][idx] if 0 <= idx < len(task['options']) else ''
        return int(answer.strip().casefold()==task['answer'].strip().casefold())
    if task['benchmark']=='gaia':
        return int(normalize_gaia(answer)==normalize_gaia(task['answer']))
    whitelist=[str(a) for group in task.get('answer_whitelist',[]) for a in group] or [task['answer']]
    norm=lambda v:re.sub(r'[^a-z0-9]','',str(v).casefold())
    return int(any(norm(answer)==norm(a) for a in whitelist))

def canonical_answer(task, answer):
    answer = str(answer or '').strip()
    if task.get('options'):
        letter = re.fullmatch(r'\(?([A-Za-z])\)?[.)]?', answer)
        if letter and 0 <= ord(letter[1].upper())-65 < len(task['options']):
            return letter[1].upper()
        for i, option in enumerate(task['options']):
            if answer.casefold() == option.strip().casefold():
                return chr(65+i)
    if task.get('benchmark') == 'gaia':
        return repr(normalize_gaia(answer))
    return re.sub(r'[^a-z0-9]', '', answer.casefold())

def should_route(public,draft,independent,threshold=0):
    """Only task metadata and preceding candidate records enter the policy."""
    a=str(draft.get('final_answer') or '').strip()
    b=str(independent.get('final_answer') or '').strip()
    if not a or not b:return False
    if canonical_answer(public,a)!=canonical_answer(public,b):return False
    def confidence(candidate):
        try:return min(1,max(0,float(candidate.get('confidence',0))))
        except (TypeError,ValueError):return 0
    return min(confidence(draft),confidence(independent))>=threshold
