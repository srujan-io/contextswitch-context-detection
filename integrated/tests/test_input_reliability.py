import math
import struct
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from vision.pose_filter import eye_roll, OneEuro, matrix_pose
from vision.gestures import GestureRecognizer
from voice_input import audio_levels, listen_once


def test_eye_roll_has_no_360_degree_jump_at_neutral():
    assert abs(eye_roll(-100, .1)-eye_roll(-100,-.1)) < .2
    assert eye_roll(-100,0)==0
    assert eye_roll(100,0)==0
    assert eye_roll(100,10)>0


def test_filter_suppresses_jitter_without_freezing_motion():
    f=OneEuro();f.update(0,0)
    outputs=[f.update((-1)**i, .033*(i+1)) for i in range(20)]
    assert max(abs(x) for x in outputs)<.6
    for i in range(20): value=f.update(15,1+i*.033)
    assert value>14


@pytest.mark.parametrize('axis', ['pitch','yaw','roll'])
def test_matrix_pose_ignores_translation_and_recovers_rotation(axis):
    theta=math.radians(15);c,s=math.cos(theta),math.sin(theta)
    rotations={'pitch':[[1,0,0],[0,c,-s],[0,s,c]],'yaw':[[c,0,s],[0,1,0],[-s,0,c]],'roll':[[c,-s,0],[s,c,0],[0,0,1]]}
    matrix=[row+[123+i*50] for i,row in enumerate(rotations[axis])]+[[0,0,0,1]]
    pose=matrix_pose(matrix)
    assert pose[axis]==pytest.approx(15)
    for other in {'pitch','yaw','roll'}-{axis}: assert abs(pose[other])<1e-6


def test_native_capture_uses_selected_device_rate_and_releases_driver(monkeypatch):
    from audio_capture import capture_fixed
    calls=[]
    class Recording:
        def tobytes(self):return b'\0\0'*480
    fake=SimpleNamespace(default=SimpleNamespace(device=[2,0]),query_devices=lambda i,kind:{'max_input_channels':1,'default_samplerate':48000,'name':'Headset'},
                         check_input_settings=lambda **kw:calls.append(('check',kw)),rec=lambda n,**kw:(calls.append(('record',n,kw)) or Recording()),
                         wait=lambda:calls.append(('wait',)),stop=lambda:calls.append(('stop',)))
    monkeypatch.setitem(sys.modules,'sounddevice',fake)
    phases=[]
    audio=capture_fixed(2,5,lambda p,d:phases.append(p))
    assert audio.sample_rate==48000
    assert calls[1][1]==240000 and calls[1][2]['device']==2
    assert calls[-1]==('stop',)
    assert phases==['RECORDING']


def test_head_rearms_after_a_neutral_hold_and_can_fire_again():
    g=GestureRecognizer();neutral={'pitch':0,'yaw':0,'roll':0,'valid_for_actions':True};g.calibrate(neutral)
    pose={**neutral,'yaw':15}
    with patch('vision.gestures.time.monotonic',return_value=10):assert g.process(pose) is None
    with patch('vision.gestures.time.monotonic',return_value=10.2):assert g.process(pose)['action']=='NEXT_PAGE'
    for i in range(20):
        with patch('vision.gestures.time.monotonic',return_value=11+i*.033):g.process(neutral)
    assert g.armed and g.state=='NEUTRAL'
    emitted=[]
    for i in range(20):
        with patch('vision.gestures.time.monotonic',return_value=12+i*.033):
            event=g.process(pose)
            if event: emitted.append(event)
    assert len(emitted)==1


def test_invalid_angles_never_fire():
    g=GestureRecognizer()
    assert g.process({'valid_for_actions':True,'pitch':math.nan,'yaw':0,'roll':0}) is None


def test_calibration_is_time_based_and_works_at_low_frame_rates():
    neutral={'pitch':15,'yaw':0,'roll':0,'valid_for_actions':True};g=GestureRecognizer()
    for i in range(8):
        with patch('vision.gestures.time.monotonic',return_value=i*.2):g.process(neutral)
    assert g.neutral is not None and g.state=='NEUTRAL'
    assert g.process(neutral) is None
    assert g.last_delta['pitch']==0


def test_calibration_cannot_finish_on_a_fast_burst_of_frames():
    g=GestureRecognizer();neutral={'pitch':0,'yaw':0,'roll':0,'valid_for_actions':True}
    for i in range(20):
        with patch('vision.gestures.time.monotonic',return_value=i*.01):g.process(neutral)
    assert g.neutral is None


def test_motion_during_calibration_resets_stable_window():
    g=GestureRecognizer();neutral={'pitch':0,'yaw':0,'roll':0,'valid_for_actions':True}
    for i in range(8):
        with patch('vision.gestures.time.monotonic',return_value=i*.2):g.process({**neutral,'pitch':i*3})
    assert g.neutral is None and g.calibration_since is None


class Audio:
    sample_rate=16000
    def __init__(self,value=500):self.pcm=struct.pack('<h',value)*16000
    def get_raw_data(self,**kwargs):return self.pcm


def test_audio_diagnostics_distinguish_muted_quiet_and_clipped():
    assert audio_levels(Audio(0))['level_hint']=='SILENT'
    assert audio_levels(Audio(30))['level_hint']=='VERY_QUIET'
    assert audio_levels(Audio(32767))['level_hint']=='CLIPPING'


def test_fixed_recording_does_not_consume_first_word_in_calibration(monkeypatch):
    calls=[]
    class Recognizer:
        def record(self,source,duration):calls.append(('record',duration));return Audio()
        def listen(self,*args,**kwargs):raise AssertionError('Fixed capture must not use VAD')
        def recognize_google(self,audio,language):calls.append(('language',language));return 'scroll down'
    class Mic:
        def __init__(self,device_index):calls.append(('device',device_index))
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setitem(sys.modules,'speech_recognition',SimpleNamespace(Recognizer=Recognizer,Microphone=Mic))
    class Router:
        def handle_text(self,text,*args):return {'transcript':text}
    phases=[]
    result=listen_once('PCB_WEB','KICAD_SCHEMATIC',device_index=3,language='en-IN',router=Router(),capture_seconds=5,phase_callback=lambda phase,detail:phases.append(phase))
    assert result['voice_event']['text']=='scroll down'
    assert calls==[('device',3),('record',5),('language','en-IN')]
    assert phases==['RECORDING','TRANSCRIBING']


def test_native_voice_auto_stops_after_speech_without_losing_opening_audio(monkeypatch):
    np=pytest.importorskip('numpy')
    from audio_capture import capture_utterance
    reads=[]
    class Stream:
        def __init__(self,**kwargs):self.i=0
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):
            self.i+=1;reads.append(self.i)
            return np.full((n,1),1000 if self.i<=6 else 0,dtype=np.int16),False
    fake=SimpleNamespace(default=SimpleNamespace(device=[1,0]),query_devices=lambda *a:{'default_samplerate':1000,'name':'Headset'},InputStream=Stream)
    monkeypatch.setitem(sys.modules,'sounddevice',fake)
    audio=capture_utterance(1,5,None)
    assert len(reads)==16  # 300 ms speech + 500 ms silence, not a fixed 5 seconds.
    assert audio.frame_data[:2]==struct.pack('<h',1000)
