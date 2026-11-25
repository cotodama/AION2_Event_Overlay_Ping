"""One persistent shared WASAPI stream for this application's alerts and mixer."""
import array
from collections import deque
import json
import os
from pathlib import Path
import queue
import threading
import time

APP_AUDIO_NAME='AION2 Event Overlay Ping'
RATE=48000
CHANNELS=2

class Voice:
    def __init__(self,decoder,gain):
        self.decoder=decoder;self.gain=gain;self.chunks=deque();self.offset=0;self.ended=False
    def close(self):
        try:self.decoder.close()
        except Exception:pass

class AppAudio:
    def __init__(self,icon_path=None,data_dir=None):
        self.icon_path=str(icon_path or '');self.data_dir=Path(data_dir) if data_dir else None
        self.stop=threading.Event();self.ready=threading.Event();self.device_stopped=threading.Event()
        self.lock=threading.Lock();self.requests=queue.Queue(maxsize=32);self.voices={}
        self.error='';self.backend='';self.sessions=[];self.callback_error=''
        self.rendered_frames=0;self.nonzero_frames=0;self.last_peak=0.;self.completed_channels=[]
        self.device=None;self._log_state=None;self.controls=queue.Queue()
        self.worker=threading.Thread(target=self._run,name='AION2 application audio',daemon=True);self.worker.start()

    def play_file(self,path,gain=1.,channel='event',fallback=None,fallback_gain=1.):
        if self.stop.is_set():return False
        if not Path(path).is_file() and not (fallback and Path(fallback).is_file()):return False
        request=(str(path),max(0.,min(1.,float(gain))),str(channel),str(fallback or ''),float(fallback_gain))
        try:self.requests.put_nowait(request);return True
        except queue.Full:return False

    def _render(self,frames):
        count=int(frames)*CHANNELS
        if count<=0:return b''
        with self.lock:
            self.rendered_frames+=frames
            active=[voice for voice in self.voices.values() if voice.chunks]
            if not active:return bytes(count*4)
            mixed=array.array('f',[0.])*count
            for voice in active:
                index=0
                while index<count and voice.chunks:
                    chunk=voice.chunks[0];take=min(count-index,len(chunk)-voice.offset)
                    for n in range(take):mixed[index+n]+=chunk[voice.offset+n]*voice.gain
                    voice.offset+=take;index+=take
                    if voice.offset>=len(chunk):voice.chunks.popleft();voice.offset=0
            peak=0.
            for n,value in enumerate(mixed):
                value=max(-1.,min(1.,value));mixed[n]=value;peak=max(peak,abs(value))
            if peak>0:self.nonzero_frames+=frames;self.last_peak=peak
            return mixed

    def mixer_status(self,volume=None,mute=None,timeout=3):
        done=threading.Event();answer={}
        self.controls.put((volume,mute,done,answer))
        if not done.wait(timeout):raise TimeoutError('Application audio session is not ready')
        if 'error' in answer:raise OSError(answer['error'])
        return answer['value']

    def _log(self):
        state=(self.ready.is_set(),self.error,self.backend,len(self.sessions))
        if state==self._log_state or not self.data_dir:return
        self._log_state=state
        try:
            self.data_dir.mkdir(parents=True,exist_ok=True)
            target=self.data_dir/'audio_status.json';temp=target.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(ready=state[0],error=self.error,backend=self.backend,
                mixer_name=APP_AUDIO_NAME,session_count=len(self.sessions),pid=os.getpid()),ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(target)
        except OSError:pass

    def _open(self,module):
        from wasapi_output import WasapiOutput
        self.device_stopped.clear()
        self.device=WasapiOutput(APP_AUDIO_NAME,self.icon_path,self._render)
        self.sessions=[self.device.status()]
        self.backend=self.device.backend;self.error='';self.ready.set()

    def _fill(self,module):
        while True:
            try:path,gain,channel,fallback,fallback_gain=self.requests.get_nowait()
            except queue.Empty:break
            decoder=None
            for candidate,level in ((path,gain),(fallback,fallback_gain)):
                if not candidate:continue
                try:
                    decoder=module.stream_file(candidate,output_format=module.SampleFormat.FLOAT32,
                        nchannels=CHANNELS,sample_rate=RATE,frames_to_read=4096)
                    first=next(decoder)
                    if not first:raise ValueError('Empty audio file')
                    voice=Voice(decoder,level);voice.chunks.append(first)
                    with self.lock:old=self.voices.pop(channel,None);self.voices[channel]=voice
                    if old:old.close()
                    self.error=''
                    break
                except Exception as exc:
                    if decoder:
                        try:decoder.close()
                        except Exception:pass
                    decoder=None;self.error='音声ファイルの読み込み失敗: '+str(exc)
            if decoder is None:self._log()
        with self.lock:voices=list(self.voices.items())
        for channel,voice in voices:
            for _ in range(6):
                with self.lock:needed=len(voice.chunks)<12 and not voice.ended
                if not needed:break
                try:chunk=next(voice.decoder)
                except StopIteration:voice.ended=True;break
                except Exception as exc:voice.ended=True;self.error='音声デコード失敗: '+str(exc);break
                with self.lock:voice.chunks.append(chunk)
            with self.lock:
                finished=voice.ended and not voice.chunks and self.voices.get(channel) is voice
                if finished:self.voices.pop(channel);self.completed_channels.append(channel)
            if finished:voice.close()

    def _close_device(self):
        self.ready.clear()
        if self.device:
            try:self.device.close()
            except Exception:pass
            self.device=None

    def _run(self):
        try:
            import miniaudio
        except Exception as exc:self.error='音声ライブラリを開始できません: '+str(exc);self._log();return
        identity_at=0.
        try:
            while not self.stop.is_set():
                if self.device is None or self.device_stopped.is_set():
                    self._close_device()
                    try:self._open(miniaudio);identity_at=0.
                    except Exception as exc:
                        self.error='音声出力を開始できません: '+str(exc);self._log()
                        self.stop.wait(2);continue
                self._fill(miniaudio)
                try:
                    self.device.pump()
                    while True:
                        try:volume,mute,done,answer=self.controls.get_nowait()
                        except queue.Empty:break
                        try:answer['value']=self.device.status(volume,mute)
                        except Exception as exc:answer['error']=str(exc)
                        finally:done.set()
                except Exception as exc:
                    self.error='音声出力の再接続待ち: '+str(exc);self._log();self._close_device()
                    self.stop.wait(1);continue
                if time.monotonic()>=identity_at:
                    try:
                        if self.device.default_changed():self._close_device();continue
                        self.sessions=[self.device.status()]
                    except Exception as exc:
                        self.error='音声デバイスの再接続待ち: '+str(exc);self._log();self._close_device()
                        self.stop.wait(1);continue
                    identity_at=time.monotonic()+1
                    if self.callback_error:self.error='音声描画エラー: '+self.callback_error
                    self._log()
                self.stop.wait(.02)
        finally:
            self._close_device()
            with self.lock:voices=list(self.voices.values());self.voices.clear()
            for voice in voices:voice.close()

    def close(self):
        self.stop.set()
        if threading.current_thread() is not self.worker:self.worker.join(timeout=2)
