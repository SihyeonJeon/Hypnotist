import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from confab_ctx import context, transcripts


class RecipientContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sid = str(uuid.uuid4())
        for name in ("CLAUDE_ROOT", "CODEX_ROOT"):
            mock = patch.object(transcripts, name, self.root / name)
            mock.start()
            self.addCleanup(mock.stop)

    def write(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def test_claude_follows_selected_branch(self):
        rows = []
        for uid, parent, role, text in [('a',None,'user','Inspect the sample.'),
                                        ('b','a','assistant','Old branch'),
                                        ('c','a','assistant','The fixture is ready.'),
                                        ('d','c','user','Run the local test only.')]:
            rows.append(dict(type=role, uuid=uid, parentUuid=parent, sessionId=self.sid,
                             cwd='/work/sample', message=dict(role=role, content=text)))
        self.write(transcripts.CLAUDE_ROOT/'projects'/'sample'/(self.sid+'.jsonl'),rows)
        result = context.recent_context(self.sid)
        self.assertEqual([m['text'] for m in result['turns']],
                         ['Inspect the sample.','The fixture is ready.','Run the local test only.'])
        self.assertEqual(result['cwd'],'/work/sample')

    def test_codex_ignores_other_session_and_rolled_back_work(self):
        def message(role, text):
            return dict(type='response_item', payload=dict(type='message', role=role,
                        content=[dict(type='input_text' if role=='user' else 'output_text',text=text)]))
        def meta(sid):
            return dict(type='session_meta',payload=dict(id=sid,cwd='/work/sample'))
        base = transcripts.CODEX_ROOT/'sessions'/'2026'
        self.write(base/f'rollout-1-{self.sid}.jsonl',[meta(self.sid),message('user','Keep data local.'),
                   message('assistant','Understood.'),message('user','Superseded task'),message('assistant','Old result'),
                   dict(type='event_msg',payload=dict(type='thread_rolled_back',num_turns=1))])
        self.write(base/f'rollout-2-{self.sid}-extra.jsonl',[meta(str(uuid.uuid4())),message('user','Other thread')])
        self.assertEqual([m['text'] for m in context.recent_context(self.sid)['turns']],
                         ['Keep data local.','Understood.'])
