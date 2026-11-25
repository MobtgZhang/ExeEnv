"""Exact stage-loss enumeration on saved completed trajectories."""
from collections import defaultdict
from fractions import Fraction
from itertools import product

POLICIES = ('original', 'agreement', 'fallback', 'both')
METRICS = ('correct', 'delivered', 'returned_empty', 'unavailable', 'reached_calls', 'returned_calls', 'skipped_final')
GRID = ('0', '0.01', '0.05', '0.10', '0.20', '0.30', '0.40', '1')


def simulate(state, mask, policy):
    """State contains frozen match indicators, not newly generated answers."""
    for index, available in enumerate(mask):
        if not available:
            fallback = policy in ('fallback', 'both') and index > 0 and state['draft_nonempty']
            return dict(correct=int(fallback) * state['draft_correct'], delivered=int(fallback),
                        returned_empty=0, unavailable=int(not fallback), reached_calls=index + 1,
                        returned_calls=index, skipped_final=0)
        if index == 2 and policy in ('agreement', 'both') and state['agreement']:
            return dict(correct=state['draft_correct'], delivered=1, returned_empty=0,
                        unavailable=0, reached_calls=3, returned_calls=3, skipped_final=1)
    return dict(correct=state['final_correct'], delivered=1, returned_empty=int(not state['final_nonempty']),
                unavailable=0, reached_calls=4, returned_calls=4, skipped_final=0)


def analytic(states, policy, p, dependence):
    q = 1 - p
    final = sum(s['final_correct'] for s in states)
    draft = sum(s['draft_correct'] for s in states)
    a = sum(s['draft_correct'] for s in states if s['agreement'])
    fa = sum(s['final_correct'] for s in states if s['agreement'])
    if dependence == 'common':
        return q * (final if policy in ('original', 'fallback') else final - fa + a)
    if policy == 'original':
        return q ** 4 * final
    if policy == 'agreement':
        return q ** 3 * a + q ** 4 * (final - fa)
    if policy == 'fallback':
        return q ** 4 * final + (q - q ** 4) * draft
    return q ** 3 * a + q ** 4 * (final - fa) + (q - q ** 3) * draft + q ** 3 * (1 - q) * (draft - a)


def analyze(states):
    masks = tuple(product((0, 1), repeat=4))
    counts = defaultdict(lambda: defaultdict(int))
    mask_rows = []
    for state in states:
        for mask in masks:
            for policy in POLICIES:
                result = simulate(state, mask, policy)
                key = (state['cohort'], mask, policy)
                for metric, value in result.items():
                    counts[key][metric] += value
                mask_rows.append(dict(cohort=state['cohort'], task_id=state['task_id'], mask=''.join(map(str, mask)), policy=policy, **result))
    curves = []
    for cohort in ('initial', 'extension'):
        support = [s for s in states if s['cohort'] == cohort]
        for dependence in ('independent', 'common'):
            for text in GRID:
                p = Fraction(text)
                for policy in POLICIES:
                    totals = {m: Fraction(0) for m in METRICS}
                    for mask in masks:
                        w = (1 - p) ** sum(mask) * p ** (4 - sum(mask)) if dependence == 'independent' else 1 - p if all(mask) else p if not any(mask) else Fraction(0)
                        for metric in METRICS:
                            totals[metric] += w * counts[cohort, mask, policy][metric]
                    assert totals['correct'] == analytic(support, policy, p, dependence)
                    row = dict(cohort=cohort, dependence=dependence, p=text, n=len(support), policy=policy)
                    for metric, value in totals.items():
                        row.update({f'expected_{metric}': float(value), f'{metric}_numerator': value.numerator, f'{metric}_denominator': value.denominator})
                    curves.append(row)
    return mask_rows, curves
