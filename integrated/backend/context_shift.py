"""Opt-in local threshold policy, calibrated from actual camera/audio samples."""
import time
import re
import math
from collections import deque


class ContextShift:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.enabled=False;self.started=None;self.finished=False;self.context='';self.hands_busy=False
        self.visual=deque(maxlen=2000);self.audio=deque(maxlen=1000);self.noise_limit=None
        self.audio_error=None
        self.last_audio=None
        self.duration=15.;self.baseline_rms=None;self.peak_rms=None;self.peak_amplitude=None;self.last_hands=None
        self.calibration_peak=0.
        self.current='TYPED';self.candidate=None;self.since=0.;self.reason='Automatic control is off';self.last_visual=None
    def start(self,context,hands_busy=False):
        self.enabled=True;self.started=self.clock();self.finished=False;self.context=context;self.hands_busy=hands_busy
        self.visual.clear();self.audio.clear();self.noise_limit=None;self.current='TYPED';self.candidate=None;self.reason='15-second environment calibration in progress'
        self.audio_error=None;self.last_audio=None
        self.baseline_rms=self.peak_rms=self.peak_amplitude=None
        self.calibration_peak=0.
    def observe_visual(self,head,hand,hands=None):
        now=self.clock();self.last_visual=now
        self.last_hands=hands
        usable=bool(hand) and (hands is None or hands.get('both_hands_visible',False))
        self.visual.append((now,bool(head),usable))
    def observe_audio(self,rms,peak=None):
        if not math.isfinite(rms) or rms<0 or peak is not None and not math.isfinite(peak):return
        self.last_audio=(self.clock(),float(rms))
        if self.started is not None and self.clock()-self.started<=self.duration:
            elapsed=self.clock()-self.started;amplitude=float(peak if peak is not None else rms)
            self.calibration_peak=max(self.calibration_peak,amplitude)
            if not self.audio or elapsed-self.audio[-1][0]>=.04:self.audio.append((elapsed,float(rms),amplitude))
    def choose(self,sensors,context):
        now=self.clock()
        if not self.enabled:return None
        if self.started is None or now-self.started<self.duration:return 'TYPED'
        if not self.finished:
            self.finished=True
            if self.audio:
                samples=list(self.audio)
                baseline=sorted(s[1] for s in samples if s[0]<5)
                speech=sorted(s[1] for s in samples if 5<=s[0]<10)
                self.baseline_rms=baseline[len(baseline)//2] if baseline else None
                self.peak_rms=speech[min(len(speech)-1,int(len(speech)*.95))] if speech else None
                self.peak_amplitude=self.calibration_peak
                if self.baseline_rms is not None:
                    self.noise_limit=max(200,min(self.baseline_rms*2.5,self.baseline_rms+.35*max(0,(self.peak_rms or 0)-self.baseline_rms)))
        recent=[s for s in list(self.visual) if now-s[0]<2]
        face=sum(s[1] for s in recent)/max(1,len(recent))
        hand_window=[s for s in recent if now-s[0]<.8]
        hand=sum(s[2] for s in hand_window)/max(1,len(hand_window))
        busy=self.hands_busy or bool(self.last_hands and self.last_hands.get('two_hands_possibly_occupied')) or bool(re.search(r'\b(holding|soldering|hands occupied|hands busy|carrying)\b',self.context,re.I))
        editing=context.get('selected_element',{}).get('tag') in ('input','textarea') or context.get('text_entry',False) or bool(re.search(r'\b(typing|text entry|writing)\b',self.context,re.I))
        current_hands=bool(hand_window and hand_window[-1][2] and not busy)
        voice_ready=bool(sensors.get('MICROPHONE',{}).get('status')=='AVAILABLE' and self.noise_limit is not None and self.peak_rms is not None and self.peak_rms/max(1,self.baseline_rms or 0)>=1.5 and (self.peak_amplitude or 0)<32700)
        # Idle voice is readiness, not a claim of live background recording.
        # A recent measured noise spike suppresses it; an idle mic does not expire
        # solely because the user has been controlling the page with hands.
        if voice_ready and self.last_audio and now-self.last_audio[0]<2 and self.last_audio[1]>self.noise_limit:voice_ready=False
        if editing:desired='TYPED';reason='Text-entry context; gestures suppressed'
        elif current_hands and hand>=.7:desired='HAND';reason='Two hands fully recognized; hand control is ready'
        elif voice_ready:desired='VOICE';reason='Hands missing, cropped or occupied; calibrated voice commands are ready (record on request)'
        elif face>=.7:desired='HEAD';reason='Hands unavailable; using reliable head tracking'
        else:desired='TYPED';reason='No calibrated reliable motion input'
        if desired!=self.candidate:self.candidate=desired;self.since=now
        unsafe_hand=self.current=='HAND' and not current_hands
        dwell=.5 if desired=='HAND' else 1.5
        if now-self.since>=dwell or desired=='TYPED' or unsafe_hand:self.current=desired;self.reason=reason
        return self.current
    def snapshot(self):
        elapsed=0 if self.started is None else self.clock()-self.started
        remaining=0 if self.started is None else max(0,self.duration-elapsed)
        instruction='Keep quiet; look straight ahead.' if elapsed<5 else 'Say a short sentence at normal volume; show both hands.' if elapsed<10 else 'Show both hands fully, then take your normal working posture.'
        return {'enabled':self.enabled,'calibrating':self.enabled and remaining>0,'seconds_remaining':round(remaining,1),
                'mode':self.current,'reason':self.reason,'hands_occupied':self.hands_busy,'pre_context':self.context,
                'visual_samples':len(self.visual),'audio_samples':len(self.audio),'noise_threshold_rms':self.noise_limit,
                'audio_error':self.audio_error,
                'duration_seconds':self.duration,'instruction':instruction if self.enabled and remaining>0 else 'Calibration complete' if self.finished else 'Start calibration when ready',
                'assessment_complete':self.finished,'voice_recording':'on request only',
                'baseline_rms':self.baseline_rms,'peak_rms':self.peak_rms,'peak_amplitude':self.peak_amplitude,
                'speech_to_noise_ratio':None if self.peak_rms is None or self.baseline_rms is None else round(self.peak_rms/max(1,self.baseline_rms),2),
                'hands':None if self.last_hands is None or self.last_visual is None or self.clock()-self.last_visual>.5 else {k:self.last_hands.get(k) for k in ('hand_count','fully_visible_count','both_hands_visible','two_hands_possibly_occupied','incomplete_frame')},
                'hands_detection_limit':'Visibility is not proof that hands are free; user context overrides.'}

    def sample_microphone(self,device,lock,stop):
        if not lock.acquire(blocking=False):self.audio_error='Microphone busy; audio calibration unavailable';return
        try:
            import sounddevice as sd
            import numpy as np
            def observe(data,frames,timing,status):
                self.observe_audio(float(np.sqrt(np.mean(data.astype(float)**2)))*32768,float(np.max(np.abs(data)))*32768)
            with sd.InputStream(device=device,channels=1,dtype='float32',callback=observe):
                while not stop.is_set() and self.started is not None and self.clock()-self.started<self.duration:stop.wait(.1)
        except Exception as exc:self.audio_error=str(exc)
        finally:lock.release()
