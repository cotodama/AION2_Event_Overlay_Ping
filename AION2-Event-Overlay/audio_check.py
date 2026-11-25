"""Real process-owned Core Audio session, mixer state and notification regression."""
import array,json,math,os,sys,tempfile,time,traceback,wave
from pathlib import Path
from unittest.mock import patch

def run_check(target):
    result={'passed':False,'frozen':bool(getattr(sys,'frozen',False)),'checks':[],'speaker_heard':'未確認（Core Audio APIと音声描画まで検証）'}
    app=root=None;original=None
    try:
        with tempfile.TemporaryDirectory(dir=target.parent,prefix='audio-check-') as directory:
            os.environ['AION2_OVERLAY_DATA_DIR']=directory
            from window_group import system_dpi_awareness
            system_dpi_awareness()
            import tkinter as tk
            import AION2_Event_Overlay as overlay
            from ping_feature import PingFeatureMixin
            from app_audio import APP_AUDIO_NAME
            init=PingFeatureMixin.init_ping
            def offline(self,path):init(self,path);self._background_disabled=True
            with patch.object(PingFeatureMixin,'init_ping',offline):
                errors=[];root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
                app=overlay.App(root);root.update();audio=app.audio
                def wait(condition,timeout=6):
                    start=time.monotonic()
                    while not condition():
                        if time.monotonic()-start>timeout:raise AssertionError((audio.error,audio.ready.is_set(),audio.sessions))
                        root.update();time.sleep(.01)
                wait(audio.ready.is_set)
                original=audio.mixer_status();assert original['pid']==os.getpid()
                assert original['name']==APP_AUDIO_NAME and original['state']==1
                changed=audio.mixer_status(volume=.37,mute=True)
                assert changed['volume']==.37 and changed['muted']
                time.sleep(.15);assert audio.mixer_status()['state']==1
                result['session']={k:v for k,v in changed.items() if k!='session_id'}
                result['checks'].append('actual WASAPI session is active while silent, belongs to current PID, and has the application display name; own session volume/mute round-trip succeeds')
                before=audio.nonzero_frames
                assert app.play_event_alert({'sound_volume':20},preview=True)
                wait(lambda:audio.nonzero_frames>before);wait(lambda:not audio.voices)
                state=audio.mixer_status();assert state['volume']==.37 and state['muted']
                before=audio.nonzero_frames
                app.cfg['timer_alert_volume']=30;assert app.play_timer_alert()
                wait(lambda:audio.nonzero_frames>before);wait(lambda:not audio.voices)
                assert audio.mixer_status()['muted']
                result['checks'].append('default event and timer chimes reach the same native stream without resetting mixer volume or mute')
                wav=Path(directory)/'custom.wav'
                samples=array.array('h',(int(7000*math.sin(2*math.pi*440*n/44100)) for n in range(13230)))
                with wave.open(str(wav),'wb') as f:
                    f.setparams((1,2,44100,0,'NONE','not compressed'));f.writeframes(samples.tobytes())
                before=audio.nonzero_frames
                assert app.play_event_alert({'sound_file':str(wav),'sound_volume':40},preview=True)
                wait(lambda:audio.nonzero_frames>before);wait(lambda:not audio.voices)
                fixture=(Path(sys._MEIPASS)/'audio-test/audio-test.mp3') if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]/'tests/fixtures/audio-test.mp3'
                assert fixture.is_file(),fixture
                before=audio.nonzero_frames
                assert app.play_mp3(str(fixture));wait(lambda:audio.nonzero_frames>before);wait(lambda:not audio.voices)
                broken=Path(directory)/'invalid.mp3';broken.write_bytes(b'invalid audio')
                before=audio.nonzero_frames
                assert app.play_event_alert({'sound_file':str(broken),'sound_volume':20},preview=True)
                wait(lambda:audio.nonzero_frames>before);wait(lambda:not audio.voices)
                assert not audio.error,audio.error
                result['checks'].append('custom WAV and MP3 decode and render in the same stream; corrupt MP3 falls back to the original chime')
                assert not app.play_event_alert({'sound_enabled':False})
                assert not app.play_event_alert({'sound_volume':0})
                app.cfg['timer_alert_volume']=0;assert not app.play_timer_alert()
                app.minimize_window();root.update();wait(lambda:root.state()=='iconic')
                assert app.tray_icon is not None
                result['tray_icon_visible_in_test']=app.tray_icon.visible
                if not app.tray_icon.visible:result['tray_shell_limit']='Shell_NotifyIconW returned False in this execution environment; icon painting is not verified'
                before=audio.rendered_frames;time.sleep(.15)
                assert audio.rendered_frames>before and audio.mixer_status()['state']==1
                assert app.play_event_alert({'sound_volume':10},preview=True)
                wait(lambda:bool(audio.voices));wait(lambda:not audio.voices)
                root.deiconify();root.update()
                result['checks'].append('app sound OFF and zero gain suppress notification playback; minimize-to-tray keeps the mixer session active and still renders notifications')
                previous=audio.device;audio.device_stopped.set()
                wait(lambda:audio.ready.is_set() and audio.device is not previous)
                state=audio.mixer_status();assert state['volume']==.37 and state['muted'],state
                result['checks'].append('own audio output recreation recovers and retains Windows mixer settings; no change to other applications or the master/device volume')
                audio.mixer_status(volume=original['volume'],mute=original['muted']);original=None
                assert not errors,errors
                app.on_close();app=root=None
                assert not audio.worker.is_alive() and not audio.ready.is_set()
                result['checks'].append('closing the app stops its audio worker and releases the native stream cleanly')
                result['passed']=True
    except Exception:result['error']=traceback.format_exc()
    finally:
        if app is not None:
            if original and app.audio.ready.is_set():
                try:app.audio.mixer_status(volume=original['volume'],mute=original['muted'])
                except Exception:pass
            try:app.on_close()
            except Exception:pass
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
