"""Offline reconstruction from normalized observations, never from expected tables."""
from collections import Counter, defaultdict
from math import comb, isclose, sqrt
from pathlib import Path
import json
import sqlite3
from statistics import NormalDist
from .io import read_csv, read_jsonl, write_csv, write_json, digest
from .scoring import score, should_route
from .workflow import run, parse_outer
from .faults import analyze as analyze_faults
from .attribution import attribution_tables

TABLES = ('task', 'episode', 'request', 'candidate', 'condition', 'consumes', 'depends_on')
QUERIES = ('terminal_scores', 'terminal_partition', 'candidate_selection', 'logical_usage', 'shared_failures', 'stage_funnel')


def verify_manifest(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    for name, expected in manifest['files'].items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Artifact integrity mismatch: ' + name)
    return len(manifest['files'])


def database(root, output):
    path = output / 'audit.sqlite'
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript((root / 'sql/schema.sql').read_text())
    for table in TABLES:
        columns = [r[1] for r in db.execute('PRAGMA table_info(' + table + ')')]
        rows = read_jsonl(root / 'data/primary' / (table + '.jsonl'))
        db.executemany('INSERT INTO ' + table + ' (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')',
                       [tuple(r[k] for k in columns) for r in rows])
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not list(db.execute('PRAGMA foreign_key_check'))
    db.execute('PRAGMA foreign_keys=ON')
    return db


def query(db, text):
    return [dict(r) for r in db.execute(text)]


def compare(actual, expected, keys, fields):
    aa = {tuple(str(r[k]) for k in keys): r for r in actual}
    ee = {tuple(str(r[k]) for k in keys): r for r in expected}
    assert aa.keys() == ee.keys(), (keys, 'row identities differ')
    checked = 0
    for key, row in aa.items():
        for field in fields:
            a, e = row[field], ee[key][field]
            try:
                equal = isclose(float(a), float(e), rel_tol=1e-12, abs_tol=1e-10)
            except (TypeError, ValueError):
                equal = str(a) == str(e)
            assert equal, (key, field, a, e)
            checked += 1
    return checked


def replay(root, db, tasks):
    prompts = json.loads((root / 'data/prompts.json').read_text())
    messages = {r['request_id']: r for r in read_jsonl(root / 'data/primary/messages.jsonl')}
    requests = {r['path']: r for r in read_jsonl(root / 'data/primary/request.jsonl')}
    saved_episodes = read_jsonl(root / 'data/primary/cure_episodes.jsonl')
    dependencies = defaultdict(dict)
    for r in query(db, "SELECT * FROM depends_on WHERE method='cure_l'"):
        dependencies[r['task_id']][r['stage']] = r['request_path']
    results = []
    checked_prompts = set()
    for saved in saved_episodes:
        task = tasks[saved['task_id']]
        for policy in ('original', 'fallback', 'agreement', 'both'):
            consumed = []
            def complete(stage, prompt, limit, temperature):
                identity = dependencies[task['task_id']][stage]
                record, metadata = messages[identity], requests[identity]
                assert prompt == record['messages'], (task['task_id'], stage, 'prompt differs')
                assert limit == metadata['requested_limit'] and temperature == metadata['temperature']
                checked_prompts.add(identity)
                if metadata['status'] != 'ok':
                    raise RuntimeError('Saved terminal request unavailable')
                consumed.append(metadata['tokens'])
                return record['parsed'] if record['parsed'] is not None else parse_outer(record['content'] or '')
            def observe(stage, parsed):
                return saved['observations'][0 if stage == 'ledger' else 1]
            result = run(task, complete, observe, prompts, policy)
            correct = score(task, result['prediction']) if result['status'] == 'scored' else 0
            if policy == 'original':
                assert (result['status'], result['prediction'], correct) == (saved['status'], saved.get('prediction', ''), saved['success'])
            results.append(dict(policy='agreement_fallback' if policy == 'both' else policy,
                                task_id=task['task_id'], status=result['status'], prediction=result['prediction'],
                                correct=correct, decision=result['branch'], tokens=sum(consumed)))
    original = {r['task_id']: r for r in results if r['policy'] == 'original'}
    summary = []
    for policy in ('original', 'fallback', 'agreement', 'agreement_fallback'):
        rows = [r for r in results if r['policy'] == policy]
        removed = sum(original[r['task_id']]['tokens'] - r['tokens'] for r in rows)
        total = sum(original[r['task_id']]['tokens'] for r in rows)
        summary.append(dict(policy=policy, n=len(rows), correct=sum(r['correct'] for r in rows),
                            unavailable=sum(r['status'] != 'scored' for r in rows),
                            returned_empty=sum(r['status'] == 'scored' and not r['prediction'] for r in rows),
                            answered=sum(r['status'] == 'scored' and bool(r['prediction']) for r in rows),
                            agreement=sum(r['decision'] == 'agreement' for r in rows),
                            fallback=sum(r['decision'] == 'fallback' for r in rows),
                            wins=sum(r['correct'] > original[r['task_id']]['correct'] for r in rows),
                            losses=sum(r['correct'] < original[r['task_id']]['correct'] for r in rows),
                            tokens=sum(r['tokens'] for r in rows), removed_tokens=removed, token_saving=removed/total))
    return results, summary, len(checked_prompts)


def wilson(matches, total, coverage):
    z_score = NormalDist().inv_cdf((1 + coverage) / 2)
    rate = matches / total
    denom = 1 + z_score ** 2 / total
    center = (rate + z_score ** 2 / (2 * total)) / denom
    half = z_score * sqrt(rate * (1 - rate) / total + z_score ** 2 / (4 * total ** 2)) / denom
    return center - half, center + half


def paired(episodes):
    arms = defaultdict(dict)
    for r in episodes:
        arms[r['method']][r['task_id']] = r['correct']
    rows = []
    for method, arm in sorted(arms.items()):
        if method == 'cure_l':
            continue
        wins = sum(arms['cure_l'][t] > arm[t] for t in arm)
        losses = sum(arms['cure_l'][t] < arm[t] for t in arm)
        n = wins + losses
        p = min(1, 2 * sum(comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n) if n else 1
        win_low, win_high = wilson(wins, len(arm), .975)
        loss_low, loss_high = wilson(losses, len(arm), .975)
        rows.append(dict(control=method, n=len(arm), wins=wins, losses=losses,
                         difference=(wins-losses)/len(arm), ci_low=win_low-loss_high,
                         ci_high=win_high-loss_low, exact_mcnemar_p=p))
    previous = 0
    for rank, row in enumerate(sorted(rows, key=lambda r: r['exact_mcnemar_p'])):
        previous = max(previous, min(1, (len(rows)-rank)*row['exact_mcnemar_p']))
        row['holm_p'] = previous
    return rows


def primary_trajectories(root, db, tasks):
    coverage = Counter()
    states = []
    for episode in read_jsonl(root/'data/primary/cure_episodes.jsonl'):
        if episode['status'] != 'scored':
            continue
        draft, checker, final = episode['candidates']
        task_id = episode['task_id']
        task = tasks[task_id]
        answers = [str(candidate.get('final_answer') or '') for candidate in (draft, checker, final)]
        draft_match, checker_match, final_match = [score(task, answer) for answer in answers]
        covered = max(draft_match, checker_match)
        agreement = should_route(task, draft, checker)
        states.append(dict(cohort='extension', task_id=task_id, draft_nonempty=bool(answers[0].strip()),
                           final_nonempty=bool(answers[2].strip()), agreement=agreement,
                           draft_correct=draft_match, final_correct=final_match))
        coverage.update(dict(draft=draft_match, checker=checker_match, union=covered, final=final_match,
                             checker_only=(1-draft_match)*checker_match, final_only=(1-covered)*final_match,
                             lost=covered*(1-final_match), lost_empty=covered*(1-final_match)*int(not answers[2].strip()),
                             agreement_draft=agreement*draft_match, agreement_final=agreement*final_match))
    assert len(states) == 101 and coverage == dict(draft=80, checker=65, union=84, final=76, checker_only=4,
                                                    final_only=1, lost=9, lost_empty=6, agreement_draft=61, agreement_final=63)
    shared_stages = defaultdict(dict)
    for edge in query(db, 'SELECT * FROM depends_on ORDER BY task_id,method,ordinal'):
        if edge['stage'] in ('draft', 'sample_1', 'sample_2'):
            shared_stages[(edge['task_id'], edge['stage'])][edge['method']] = edge['request_path']
    for (task_id, stage), methods in shared_stages.items():
        assert len(set(methods.values())) == 1, (task_id, stage)
        if stage == 'draft':
            assert set(methods) == {'draft', 'cure_l', 'sc', 'usc', 'cisc', 'cove', 'critic', 'self_refine', 'target_only'}
        else:
            assert set(methods) == {'sc', 'usc', 'cisc'}
    return states, dict(coverage)


def analyze(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest_count = verify_manifest(root)
    db = database(root, output)
    tasks = {r['task_id']: r for r in json.loads((root / 'data/primary/tasks.json').read_text())}
    episodes = query(db, 'SELECT * FROM episode ORDER BY method,task_id')
    for r in episodes:
        assert r['correct'] == (score(tasks[r['task_id']], r['prediction']) if r['status'] == 'scored' else 0)
    for r in query(db, 'SELECT * FROM candidate'):
        assert r['correct'] == score(tasks[r['task_id']], r['answer'])
    outputs = {}
    for name in QUERIES:
        outputs[name] = query(db, (root / 'sql' / (name + '.sql')).read_text())
        write_csv(output / (name + '.csv'), outputs[name])
    scores = []
    for method in sorted({r['method'] for r in episodes}):
        rows = [r for r in episodes if r['method'] == method]
        n, matches = len(rows), sum(r['correct'] for r in rows)
        families = defaultdict(list)
        for r in rows:
            families[tasks[r['task_id']]['subtask']].append(r['correct'])
        rate = matches/n
        ci_low, ci_high = wilson(matches, n, .95)
        tokens = sum(r['tokens'] for r in rows)
        scores.append(dict(method=method,n=n,scored=sum(r['status']=='scored' for r in rows),correct=matches,
                           accuracy=rate,ci_low=ci_low,ci_high=ci_high,
                           macro_accuracy=sum(sum(v)/len(v) for v in families.values())/len(families),
                           tokens=tokens,mean_tokens=tokens/n,
                           calls=db.execute('SELECT COUNT(*) FROM consumes WHERE method=?',(method,)).fetchone()[0]))
    write_csv(output / 'primary_scores.csv', scores)
    partitions = query(db, """SELECT method,'all' family,COUNT(*) n,SUM(repair) repair,SUM(wrong_regression) wrong_regression,
                       SUM(empty_loss) empty_loss,SUM(delivery_loss) delivery_loss,SUM(net) net FROM shared_draft_partition GROUP BY method
                       UNION ALL SELECT method,family,COUNT(*),SUM(repair),SUM(wrong_regression),SUM(empty_loss),SUM(delivery_loss),SUM(net)
                       FROM shared_draft_partition GROUP BY method,family""")
    draft = {r['task_id']: r['correct'] for r in episodes if r['method']=='draft'}
    for r in partitions:
        ids = [t for t in tasks if r['family']=='all' or tasks[t]['subtask']==r['family']]
        r['draft'] = sum(draft[t] for t in ids)
        r['final'] = r['draft']+r.pop('net')
        assert r['final']==r['draft']+r['repair']-r['wrong_regression']-r['empty_loss']-r['delivery_loss']
    write_csv(output/'primary_partition.csv',partitions)
    pool = outputs['candidate_selection']
    sc = {r['task_id']:r for r in episodes if r['method']=='sc'}
    for r in pool:
        eligible = {x['task_id'] for x in query(db,"SELECT task_id FROM candidate WHERE method='sc' GROUP BY task_id HAVING COUNT(*)=3") if sc[x['task_id']]['status']=='scored'}
        arm = {x['task_id']:x for x in episodes if x['method']==r['method']}
        r.update(pool_unavailable=len(tasks)-r['pool_available'],
                 wins_vs_sc=sum(arm[t]['correct']>sc[t]['correct'] for t in eligible if arm[t]['status']=='scored'),
                 losses_vs_sc=sum(arm[t]['correct']<sc[t]['correct'] for t in eligible if arm[t]['status']=='scored'))
    write_csv(output/'shared_pool.csv',pool)
    replay_rows, replay_summary, prompt_count = replay(root, db, tasks)
    write_csv(output/'replay_tasks.csv',replay_rows)
    write_csv(output/'replay.csv',replay_summary)
    paired_rows = paired(episodes)
    write_csv(output/'paired.csv',paired_rows)
    primary_states, completed_coverage = primary_trajectories(root, db, tasks)
    historical_states = read_jsonl(root/'data/supplementary/trajectories.jsonl')
    assert {r['task_id']: r for r in primary_states} == {r['task_id']: r for r in historical_states if r['cohort']=='extension'}
    states = [r for r in historical_states if r['cohort']=='initial'] + primary_states
    masks,curves=analyze_faults(states)
    write_csv(output/'fault_masks.csv',masks)
    write_csv(output/'fault_curves.csv',curves)
    comparisons=0
    attribution_keys = dict(completion_contrasts='method', family_attribution='family',
                            pool_strata='matches_in_pool', normalization_cases='task_id',
                            request_fanout='fanout', attempt_depth='attempt', replay_boundaries='stage')
    for name, rows in attribution_tables(db, tasks, replay_rows).items():
        write_csv(output/(name+'.csv'), rows)
        key = attribution_keys[name]
        comparisons += compare(rows, read_csv(root/'expected'/(name+'.csv')), [key],
                               [column for column in rows[0] if column != key])
    for name,actual,keys in [('primary_scores',scores,['method']),('primary_partition',partitions,['method','family']),
                             ('shared_pool',pool,['method']),('replay',replay_summary,['policy'])]:
        expected=read_csv(root/'expected'/ (name+'.csv'))
        comparisons+=compare(actual,expected,keys,[k for k in expected[0] if k not in keys])
    expected=read_csv(root/'expected/fault_curves.csv')
    for r in expected:r['p']=str(float(r['p']))
    normalized=[dict(r,p=str(float(r['p']))) for r in curves]
    comparisons+=compare(normalized,expected,['cohort','dependence','p','policy'],[k for k in expected[0] if k not in ('cohort','dependence','p','policy')])
    expected_pairs = read_csv(root/'expected/paired.csv')
    for row in expected_pairs:
        row['exact_mcnemar_p'] = row.pop('p')
    comparisons += compare(paired_rows, expected_pairs, ['control'], [key for key in paired_rows[0] if key != 'control'])
    historical=read_csv(root/'data/supplementary/replay.csv')
    comparisons+=compare(replay_rows,historical,['task_id','policy'],['status','correct'])
    requests=read_jsonl(root/'data/primary/request.jsonl')
    attempts=read_jsonl(root/'data/primary/attempt.jsonl')
    retries=dict(request_identities=len(requests),http_attempts=len(attempts),
                 failed_attempts=sum(r['status']!='ok' for r in attempts),
                 unavailable_requests=sum(r['status']!='ok' for r in requests),
                 recovered_requests=sum(r['status']=='ok' and r['failed_attempts']>0 for r in requests),
                 affected_episodes=sum(r['affected_episodes'] for r in outputs['shared_failures']),
                 physical_reported_tokens=sum(r['tokens'] or 0 for r in requests),
                 logical_reported_tokens=sum(r['tokens'] for r in episodes))
    assert retries==dict(request_identities=2259,http_attempts=6735,failed_attempts=4563,unavailable_requests=87,
                         recovered_requests=1434,affected_episodes=123,physical_reported_tokens=9540470,logical_reported_tokens=15482884)
    successful_first_attempts = sum(row['ordinal'] == 1 and row['status'] == 'ok' for row in attempts)
    failed_status_codes = Counter(row.get('http_status') for row in attempts if row['status'] != 'ok')
    distinct_affected_episodes = db.execute("""
        SELECT COUNT(*) FROM (SELECT DISTINCT d.method, d.task_id
        FROM depends_on d JOIN request r ON r.path = d.request_path WHERE r.status = 'unavailable')
    """).fetchone()[0]
    usage = [row['usage'] for row in requests if row['status'] == 'ok']
    physical_input = sum(row['prompt_tokens'] for row in usage)
    physical_output = sum(row['completion_tokens'] for row in usage)
    assert (successful_first_attempts, failed_status_codes, distinct_affected_episodes) == (738, {503: 4563}, 123)
    assert (physical_input, physical_output) == (8669334, 871136)
    retries.update(first_attempt_returns=successful_first_attempts, failed_status_codes=dict(failed_status_codes),
                   distinct_affected_episodes=distinct_affected_episodes, physical_input=physical_input, physical_output=physical_output)
    supplementary={}
    for name in ('online','temporal'):
        rows=read_csv(root/f'data/supplementary/{name}_episodes.csv')
        groups=defaultdict(list)
        for r in rows:groups[r['block'],r['arm']].append(r)
        aggregate=[dict(block=b,arm=a,n=len(g),correct=sum(int(r['success']) for r in g),unavailable=sum(r['outcome']=='unavailable' for r in g)) for (b,a),g in sorted(groups.items())]
        write_csv(output/(name+'_summary.csv'),aggregate)
        supplementary[name]=aggregate
    for name,field in [('panel_cases','consensus'),('panel_conditions','consensus'),('panel_proposals','status')]:
        rows=read_csv(root/f'data/supplementary/{name}.csv')
        counts=Counter((r.get('dimension','all'),r[field]) for r in rows)
        aggregate=[dict(dimension=d,label=l,n=n) for (d,l),n in sorted(counts.items())]
        supplementary[name]=aggregate
        write_csv(output/(name+'_summary.csv'),aggregate)
    for name in ('family_rates','initial_outcomes','initial_partitions','initial_shared_pool','layered_status','panel_strata'):
        rows=read_csv(root/f'data/supplementary/{name}.csv')
        if name=='layered_status':
            counts=Counter((r['study'],r['transport'],r['controller'],r['extraction'],r['scorer']) for r in rows)
            rows=[dict(study=k[0],transport=k[1],controller=k[2],extraction=k[3],scorer=k[4],n=v) for k,v in sorted(counts.items())]
        write_csv(output/(name+'.csv'),rows)
    summary=dict(verified=True,manifest_files=manifest_count,primary_tasks=len(tasks),primary_episodes=len(episodes),
                 exact_prompt_identities=prompt_count,scored_candidate_rows=db.execute('SELECT COUNT(*) FROM candidate').fetchone()[0],
                 expected_numeric_cells_checked=comparisons,fault_trajectories=len(states),fault_policy_masks=len(masks),
                 fault_curve_rows=len(curves),resources=retries,completed_coverage=completed_coverage,
                 primary_fault_policy_masks=len(primary_states)*16*4,supplementary=supplementary)
    write_json(output/'verification.json',summary)
    (output/'REPORT.md').write_text('# Offline reproduction report\n\nAll integrity, foreign-key, scoring, prompt replay, accounting, and expected-result comparisons passed.\n\n'
        +f"- Primary tasks: {len(tasks)}; episodes rescored: {len(episodes)}.\n- Exact saved prompt identities checked: {prompt_count}.\n- Fault policy masks: {len(masks)}; numeric comparison cells: {comparisons}.\n\n"
        +'This is reanalysis of saved observations. It is not fresh inference or expert semantic validation. Supplementary restricted-source studies are reproduced at the released observation/aggregate level.\n')
    db.close()
    return summary
