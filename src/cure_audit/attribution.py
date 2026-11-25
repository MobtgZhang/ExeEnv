"""Post-hoc attribution tables for the frozen manuscript cohort."""
from collections import Counter, defaultdict
from .scoring import canonical_answer


def attribution_tables(db, tasks, replay_rows):
    episodes = defaultdict(dict)
    for row in db.execute('SELECT * FROM episode ORDER BY method, task_id'):
        episodes[row['method']][row['task_id']] = row
    methods = ('direct', 'draft', 'self_refine', 'sc', 'usc', 'cisc', 'cove', 'critic', 'target_only')
    cure = episodes['cure_l']
    contrasts = []
    for method in methods:
        values = Counter()
        for task_id, target in cure.items():
            control = episodes[method][task_id]
            target_returns = target['status'] == 'scored'
            control_returns = control['status'] == 'scored'
            if target_returns and control_returns:
                values['both'] += 1
                values['both_net'] += target['correct'] - control['correct']
            elif target_returns:
                values['target_only'] += 1
                values['target_only_matches'] += target['correct']
            elif control_returns:
                values['control_only'] += 1
                values['control_only_matches'] += control['correct']
            else:
                values['neither'] += 1
        net = sum(cure[task_id]['correct'] - episodes[method][task_id]['correct'] for task_id in cure)
        assert net == values['both_net'] + values['target_only_matches'] - values['control_only_matches']
        lower = net - values['target_only'] - values['neither']
        upper = net + values['control_only'] + values['neither']
        contrasts.append(dict(method=method, both=values['both'], both_net=values['both_net'],
                              target_only=values['target_only'], target_only_matches=values['target_only_matches'],
                              control_only=values['control_only'], control_only_matches=values['control_only_matches'],
                              neither=values['neither'], observed_net=net, lower=lower, upper=upper))

    families = [dict(row) for row in db.execute('''
        SELECT family, COUNT(*) AS n, SUM(d.correct) AS draft_matches,
               SUM(q.correct) AS final_matches, SUM(q.status='scored') AS returned,
               SUM(p.repair) AS repairs, SUM(p.wrong_regression) AS wrong_loss,
               SUM(p.empty_loss) AS empty_loss, SUM(p.delivery_loss) AS delivery_loss
        FROM shared_draft_partition p
        JOIN episode d ON d.task_id=p.task_id AND d.method='draft'
        JOIN episode q ON q.task_id=p.task_id AND q.method=p.method
        WHERE p.method='cure_l' GROUP BY family ORDER BY family
    ''')]
    for row in families:
        assert row['final_matches'] - row['draft_matches'] == (
            row['repairs'] - row['wrong_loss'] - row['empty_loss'] - row['delivery_loss'])

    pools = Counter()
    normalization_cases = []
    for row in db.execute('''
        SELECT c.task_id, SUM(c.correct) AS matches FROM candidate c
        JOIN episode e USING (method, task_id) WHERE c.method='sc' AND e.status='scored'
        GROUP BY c.task_id HAVING COUNT(*)=3
    '''):
        task_id, multiplicity = row
        reference = episodes['sc'][task_id]
        pools[multiplicity, 'n'] += 1
        pools[multiplicity, 'sc_matches'] += reference['correct']
        if multiplicity >= 2 and not reference['correct']:
            task = tasks[task_id]
            candidates = db.execute('''
                SELECT answer, correct FROM candidate WHERE method='sc' AND task_id=? ORDER BY ordinal
            ''', (task_id,)).fetchall()
            keys = {canonical_answer(task, candidate['answer']) for candidate in candidates}
            normalization_cases.append(dict(task_id=task_id, pool_matches=multiplicity,
                                            ballot_groups=len(keys), options=len(task['options']),
                                            raw_answers='|'.join(candidate['answer'] for candidate in candidates),
                                            selected_answer=reference['prediction'],
                                            selected_group=canonical_answer(task, reference['prediction'])))
        for method in ('usc', 'cisc'):
            selected = episodes[method][task_id]
            returned = selected['status'] == 'scored'
            pools[multiplicity, method+'_returned'] += returned
            pools[multiplicity, method+'_matches'] += selected['correct']
            pools[multiplicity, method+'_answer_diff'] += returned and (
                canonical_answer(tasks[task_id], selected['prediction']) !=
                canonical_answer(tasks[task_id], reference['prediction']))
    pool_columns = ('n', 'sc_matches', 'usc_returned', 'usc_matches', 'usc_answer_diff',
                    'cisc_returned', 'cisc_matches', 'cisc_answer_diff')
    pool_strata = [dict(matches_in_pool=multiplicity, **{
        column: pools[multiplicity, column] for column in pool_columns}) for multiplicity in range(4)]

    fanout = [dict(row) for row in db.execute('''
        WITH dep AS (
            SELECT request_path, COUNT(*) AS fanout
            FROM (SELECT DISTINCT request_path, method, task_id FROM depends_on)
            GROUP BY request_path
        ), used AS (
            SELECT request_path, COUNT(*) AS uses FROM consumes GROUP BY request_path
        )
        SELECT dep.fanout, COUNT(*) AS requests, SUM(r.status='unavailable') AS unavailable,
               SUM(CASE WHEN r.status='unavailable' THEN dep.fanout ELSE 0 END) AS failed_edges,
               SUM(COALESCE(r.tokens, 0)) AS physical_tokens,
               SUM(COALESCE(r.tokens * used.uses, 0)) AS logical_tokens
        FROM request r JOIN dep ON dep.request_path=r.path LEFT JOIN used ON used.request_path=r.path
        GROUP BY dep.fanout ORDER BY dep.fanout
    ''')]
    assert sum(row['requests'] for row in fanout) == db.execute('SELECT COUNT(*) FROM request').fetchone()[0]
    assert sum(row['logical_tokens'] for row in fanout) == sum(
        row['tokens'] for method in episodes.values() for row in method.values())

    attempt_depth = []
    for depth in range(1, 9):
        reached, returned = db.execute('''
            SELECT COUNT(*), SUM(status='ok' AND failed_attempts=?)
            FROM request WHERE failed_attempts + (status='ok') >= ?
        ''', (depth - 1, depth)).fetchone()
        attempt_depth.append(dict(attempt=depth, reached=reached, returned=returned,
                                  still_unavailable=reached-returned))
    assert sum(row['returned'] for row in attempt_depth) == db.execute(
        "SELECT COUNT(*) FROM request WHERE status='ok'").fetchone()[0]

    replays = {(row['task_id'], row['policy']): row for row in replay_rows}
    boundaries = defaultdict(Counter)
    for row in db.execute('''
        SELECT d.task_id, d.stage FROM depends_on d JOIN request r ON r.path=d.request_path
        WHERE d.method='cure_l' AND r.status='unavailable'
    '''):
        task_id, stage = row
        assert replays[task_id, 'original']['status'] != 'scored'
        values = boundaries[stage]
        values['n'] += 1
        values['matching_draft'] += episodes['draft'][task_id]['correct']
        values['prefix_tokens'] += cure[task_id]['tokens']
        for policy in ('fallback', 'agreement', 'agreement_fallback'):
            result = replays[task_id, policy]
            values[policy+'_returns'] += result['status'] == 'scored'
            values[policy+'_matches'] += result['correct']
    boundary_columns = ('n', 'matching_draft', 'prefix_tokens', 'fallback_returns', 'fallback_matches',
                        'agreement_returns', 'agreement_matches', 'agreement_fallback_returns',
                        'agreement_fallback_matches')
    stages = ('draft', 'ledger', 'independent_solution', 'final_answer')
    policy_boundaries = [dict(stage=stage, **{
        column: boundaries[stage][column] for column in boundary_columns}) for stage in stages]
    assert sum(row['n'] for row in policy_boundaries) == sum(row['status'] != 'scored' for row in cure.values())
    return dict(completion_contrasts=contrasts, family_attribution=families, pool_strata=pool_strata,
                normalization_cases=normalization_cases, request_fanout=fanout,
                attempt_depth=attempt_depth, replay_boundaries=policy_boundaries)
