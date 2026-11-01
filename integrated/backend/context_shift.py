"""Opt-in local threshold policy, calibrated from actual camera/audio samples."""
import time
import re
from collections import deque


class ContextShift:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.enabled=False;self.started=None;self.finished=False;self.context='';self.hands_busy=False
        self.visual=deque(maxlen=2000);self.audio=deque(maxlen=1000);self.noise_limit=None
        self.audio_error=None
        self.last_audio=None
        self.current='TYPED';self.candidate=None;self.since=0.;self.reason='Automatic control is off';self.last_visual=None
    def start(self,context,hands_busy=False):
        self.enabled=True;self.started=self.clock();self.finished=False;self.context=context;self.hands_busy=hands_busy
        self.visual.clear();self.audio.clear();self.noise_limit=None;self.current='TYPED';self.candidate=None;self.reason='20-second calibration in progress'
        self.audio_error=None;self.last_audio=None
    def observe_visual(self,head,hand):
        now=self.clock();self.last_visual=now
        self.visual.append((now,bool(head),bool(hand)))
    def observe_audio(self,rms):
        self.last_audio=(self.clock(),float(rms))
        if self.started is not None and self.clock()-self.started<=20:self.audio.append(float(rms))
    def choose(self,sensors,context):
        now=self.clock()
        if not self.enabled:return None
        if self.started is None or now-self.started<20:return 'TYPED'
        if not self.finished:
            self.finished=True
            if self.audio:
                ordered=sorted(self.audio);self.noise_limit=max(200,ordered[len(ordered)//2]*2.5)
        recent=[s for s in self.visual if now-s[0]<2]
        face=sum(s[1] for s in recent)/max(1,len(recent));hand=sum(s[2] for s in recent)/max(1,len(recent))
        busy=self.hands_busy or bool(re.search(r'\b(holding|soldering|hands occupied|hands busy|carrying)\b',self.context,re.I))
        editing=context.get('selected_element',{}).get('tag') in ('input','textarea') or context.get('text_entry',False) or bool(re.search(r'\b(typing|text entry|writing)\b',self.context,re.I))
        if editing:desired='TYPED';reason='Text-entry context; gestures suppressed'
        elif not busy and hand>=.7:desired='HAND';reason='Hand visible and user has not marked hands occupied'
        elif face>=.7:desired='HEAD';reason='Reliable head tracking; hands unavailable or occupied'
        elif sensors.get('MICROPHONE',{}).get('status')=='AVAILABLE' and self.audio and self.noise_limit is not None and self.last_audio and now-self.last_audio[0]<30 and self.last_audio[1]<=self.noise_limit:
            desired='VOICE';reason='Camera inputs unavailable; microphone capture calibrated'
        else:desired='TYPED';reason='No calibrated reliable motion input'
        if desired!=self.candidate:self.candidate=desired;self.since=now
        if now-self.since>=1.5 or desired=='TYPED':self.current=desired;self.reason=reason
        return self.current
    def snapshot(self):
        remaining=0 if self.started is None else max(0,20-(self.clock()-self.started))
        return {'enabled':self.enabled,'calibrating':self.enabled and remaining>0,'seconds_remaining':round(remaining,1),
                'mode':self.current,'reason':self.reason,'hands_occupied':self.hands_busy,'pre_context':self.context,
                'visual_samples':len(self.visual),'audio_samples':len(self.audio),'noise_threshold_rms':self.noise_limit,
                'audio_error':self.audio_error,
                'hands_detection_limit':'Visibility is not proof that hands are free; user context overrides.'}

    def sample_microphone(self,device,lock,stop):
        if not lock.acquire(blocking=False):self.audio_error='Microphone busy; audio calibration unavailable';return
        try:
            import sounddevice as sd
            import numpy as np
            def observe(data,frames,timing,status):
                self.observe_audio(float(np.sqrt(np.mean(data.astype(float)**2)))*32768)
            with sd.InputStream(device=device,channels=1,dtype='float32',callback=observe):
                while not stop.is_set() and self.started is not None and self.clock()-self.started<20:stop.wait(.1)
        except Exception as exc:self.audio_error=str(exc)
        finally:lock.release()
