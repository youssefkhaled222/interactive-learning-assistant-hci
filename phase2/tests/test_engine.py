import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from engine import Engine

class TestEngine(unittest.TestCase):
    def setUp(self): self.e=Engine()
    def emit(self, **kw): return self.e.handle(kw)
    def test_profiles_load_different_real_content(self):
        g=self.e.view()['question']['prompt']
        b=self.emit(type='device.discovered',device_id='demo-device-beginner',source='simulator')
        a=self.emit(type='device.discovered',device_id='demo-device-advanced',source='simulator')
        self.assertNotEqual(g,b['question']['prompt'])
        self.assertNotEqual(b['question']['prompt'],a['question']['prompt'])
        self.assertEqual(a['user_id'],'learner_02')
    def test_unknown_device_stays_guest(self):
        x=self.emit(type='device.discovered',device_id='someone-else-device',source='bleak')
        self.assertEqual(x['level'],'guest')
    def test_wrong_answer_retries_same_question(self):
        self.emit(type='device.discovered',device_id='demo-device-beginner')
        x=self.emit(type='game.select',object='book')
        self.assertEqual(x['question_index'],0)
        self.assertEqual(x['wrong_attempts'],1)
        x=self.emit(type='game.select',object='apple')
        self.assertEqual(x['question_index'],1)
        self.assertEqual(x['first_try_correct'],0)
    def test_completed_and_first_try_separate(self):
        self.emit(type='device.discovered',device_id='demo-device-beginner')
        for choice in ['apple','cup','book','apple','cup']:
            x=self.emit(type='game.select',object=choice)
        self.assertTrue(x['completed'])
        self.assertEqual(x['question_index'],5)
        self.assertEqual(x['first_try_correct'],5)
    def test_tracking_loss(self):
        x=self.emit(type='pose.tracking',visible=False,source='mediapipe')
        self.assertFalse(x['tracking'])
        self.assertIn('lost',x['status'].lower())
    def test_invalid_event(self):
        with self.assertRaises(ValueError): self.e.handle({'hello':'world'})

if __name__=='__main__':unittest.main()
