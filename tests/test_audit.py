"""Behavioral checks for public-input isolation, routing, faults, and integrity."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from cure_audit.analysis import verify_manifest
from cure_audit.scoring import canonical_answer, public_task, score
from cure_audit.workflow import run
from cure_audit.faults import simulate, analytic


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.task=dict(benchmark='lab_bench',question='Choose.',options=['enzyme','buffer'],answer='enzyme',
                       context={'protocol':'Visible input','answer':'Never show'},evaluation={'correct':True})
        self.prompts={k:k for k in ('SYSTEM','FORMAT','LEDGER','CHALLENGE','FINAL')}

    def test_private_evaluator_never_enters_prompt(self):
        public=public_task(self.task)
        self.assertEqual(set(public),{'question','options','evidence'})
        self.assertEqual(public['evidence'],{'protocol':'Visible input'})
        seen=[]
        def complete(stage,messages,limit,temp):
            seen.extend(messages)
            return {'final_answer':'A'}
        run(self.task,complete,lambda *args:{'status':'absent','seconds':0},self.prompts)
        self.assertNotIn('Never show',json.dumps(seen))
        self.assertNotIn('evaluation',json.dumps(seen))

    def test_strict_score_accepts_choice_not_explanation(self):
        self.assertEqual(score(self.task,'(A)'),1)
        self.assertEqual(score(self.task,'enzyme'),1)
        self.assertEqual(score(self.task,'A because enzyme'),0)
        self.assertEqual(score(self.task,''),0)

    def test_vote_normalization_does_not_change_frozen_scoring(self):
        task = dict(self.task, options=['A', 'G', 'R', 'T'], answer='R')
        self.assertEqual(canonical_answer(public_task(task), 'R'), 'C')
        self.assertEqual(score(task, 'R'), 0)
        self.assertEqual(score(task, 'C'), 1)

    def test_agreement_skips_only_final(self):
        stages=[]
        def complete(stage,*args):
            stages.append(stage)
            return {'final_answer':'A' if stage=='draft' else 'enzyme'}
        result=run(self.task,complete,lambda *args:{'seconds':1},self.prompts,'agreement')
        self.assertEqual(result['branch'],'agreement')
        self.assertEqual(stages,['draft','ledger','independent_solution'])

    def test_fallback_requires_returned_nonempty_draft(self):
        def complete(stage,*args):
            if stage!='draft':raise RuntimeError('unavailable')
            return {'final_answer':'A'}
        self.assertEqual(run(self.task,complete,lambda *args:{},self.prompts,'fallback')['prediction'],'A')
        self.assertEqual(run(self.task,complete,lambda *args:{},self.prompts)['status'],'unavailable')
        def unavailable(*args):raise RuntimeError('unavailable')
        self.assertEqual(run(self.task,unavailable,lambda *args:{},self.prompts,'fallback')['status'],'unavailable')

    def test_explicit_empty_final_is_not_transport_failure(self):
        def complete(stage,*args):return {'final_answer':'' if stage=='final_answer' else 'A'}
        result=run(self.task,complete,lambda *args:{},self.prompts,'fallback')
        self.assertEqual((result['status'],result['prediction']),('scored',''))

    def test_loss_dependence_changes_retention_benefit(self):
        state=dict(draft_correct=1,final_correct=0,draft_nonempty=True,final_nonempty=True,agreement=False)
        p=Fraction(1,10)
        self.assertEqual(analytic([state],'fallback',p,'common'),0)
        self.assertGreater(analytic([state],'fallback',p,'independent'),0)
        self.assertEqual(simulate(state,(0,1,1,1),'fallback')['correct'],0)
        self.assertEqual(simulate(state,(1,0,1,1),'fallback')['correct'],1)

    def test_manifest_rejects_tampering(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'input.txt';path.write_text('frozen')
            (root/'MANIFEST.json').write_text(json.dumps({'files':{'input.txt':hashlib.sha256(path.read_bytes()).hexdigest()}}))
            self.assertEqual(verify_manifest(root),1)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'integrity mismatch'):verify_manifest(root)

    def test_failed_requests_are_dependencies_not_consumptions(self):
        def rows(name):
            return [json.loads(line) for line in (ROOT/f'data/primary/{name}.jsonl').read_text().split('\n') if line]
        failed={r['path'] for r in rows('request') if r['status']!='ok'}
        self.assertEqual(len(failed),87)
        self.assertFalse(failed & {r['request_path'] for r in rows('consumes')})
        self.assertEqual(sum(r['request_path'] in failed for r in rows('depends_on')),123)


if __name__=='__main__':unittest.main()
