import array,sys,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from app_audio import AppAudio,Voice

class AudioTests(unittest.TestCase):
    def engine(self):
        engine=AppAudio.__new__(AppAudio);engine.lock=threading.Lock();engine.voices={}
        engine.rendered_frames=engine.nonzero_frames=0;engine.last_peak=0
        return engine
    def test_idle_is_silent_and_does_not_end_the_stream(self):
        engine=self.engine()
        for _ in range(3):self.assertEqual(engine._render(4),bytes(32))
        self.assertEqual(engine.rendered_frames,12);self.assertEqual(engine.nonzero_frames,0)
    def test_independent_event_timer_gains_mix_and_clip(self):
        engine=self.engine()
        for key,gain in [('event',.5),('timer',.25)]:
            voice=Voice(None,gain);voice.chunks.append(array.array('f',[1.,-1.,1.,-1.]))
            engine.voices[key]=voice
        self.assertEqual(list(engine._render(2)),[.75,-.75,.75,-.75])
        self.assertEqual(engine.nonzero_frames,2)
        voice=Voice(None,1.);voice.chunks.append(array.array('f',[2.,-2.]))
        engine.voices={'event':voice};self.assertEqual(list(engine._render(1)),[1.,-1.])
    def test_partial_chunks_do_not_drop_or_repeat_frames(self):
        engine=self.engine();voice=Voice(None,1.)
        voice.chunks.extend([array.array('f',[.25,.5]),array.array('f',[.75,1.])]);engine.voices={'event':voice}
        self.assertEqual(list(engine._render(1)),[.25,.5])
        self.assertEqual(list(engine._render(2)),[.75,1.,0.,0.])
        self.assertFalse(voice.chunks)
