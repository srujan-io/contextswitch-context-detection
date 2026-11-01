"""IMU samples in this file are simulated INTERNAL samples, never hardware packets."""
import math
from unittest.mock import patch
import pytest
from motion import ClockAlignment, PoseFusion, Sample, SerialIMU
from context_shift import ContextShift
from vision.hand_scroll import HandScroll
from vision.gestures import GestureRecognizer
from pico_imu import Decoder

def pose(p=0,y=0,r=0):return {'pitch':p,'yaw':y,'roll':r,'valid_for_actions':True,'tracking_status':'TRACKING'}
def sample(t,angles=(0.,0.,0.),gyro=(0.,0.,0.),confidence=.95):return Sample(t,angles,gyro,confidence)
def calibrated():
    f=PoseFusion()
    for i in range(25):
        t=i*.05;f.ingest(sample(t,(5,0,0)),arrival=t+100);f.fuse(pose(),now=t+100)
    assert f.offset is not None
    return f

def test_timestamp_clock_offset_and_delayed_packets():
    a=ClockAlignment();assert a.align(5,100)==100
    assert a.align(5.05,100.06)==pytest.approx(100.05)
    with pytest.raises(ValueError):a.align(5.05,100.07)
    with pytest.raises(ValueError):a.align(5.1,100.5)

def test_signed_axis_mount_mapping():
    f=PoseFusion(('yaw','-pitch','roll'))
    assert f.map_axes((10,20,30))==(20,-10,30)
    with pytest.raises(ValueError):PoseFusion(('pitch','pitch','roll'))

def test_stationary_calibration_bias_and_fused_output():
    f=calibrated();assert f.mode=='FUSED'
    f.ingest(sample(1.25,(15,0,0)),101.25)
    p=f.fuse(pose(10),101.25)
    assert p['pitch']==pytest.approx(10)
    assert p['fusion_mode']=='FUSED'

def test_no_imu_only_before_calibration():
    f=PoseFusion();f.ingest(sample(0),arrival=100)
    assert not f.fuse(None,100)['valid_for_actions']

def test_dropout_fallback_and_stale_sensor_suppression():
    f=calibrated()
    assert f.fuse(None,101.22)['fusion_mode']=='IMU_ONLY'
    assert f.fuse(pose(),102)['fusion_mode']=='WEBCAM_ONLY'
    assert f.offset is None
    assert not f.fuse(None,102)['valid_for_actions']

def test_invalid_values_reset_calibration_immediately():
    f=calibrated();assert not f.ingest(sample(1.3,(math.nan,0,0)),101.3)
    assert f.offset is None and f.latest is None
    assert not f.fuse(None,101.3)['valid_for_actions']

def test_reconnect_clock_reset_cannot_reuse_calibration():
    f=calibrated();assert not f.ingest(sample(.1),101.3)
    assert f.offset is None
    f.disconnect();assert f.ingest(sample(0),200)
    assert not f.fuse(None,200)['valid_for_actions']

def test_drift_reanchoring_and_large_disagreement():
    f=calibrated();old=f.offset[0]
    for i in range(25,40):
        t=i*.05;f.ingest(sample(t,(8,0,0)),t+100);f.fuse(pose(),t+100)
    assert f.offset[0]<old
    f.ingest(sample(2,(80,0,0)),102)
    assert f.fuse(pose(),102)['fusion_mode']=='WEBCAM_ONLY'
    assert f.offset is None

def test_gyro_prediction_uses_aligned_packet_age():
    f=calibrated();f.ingest(sample(1.25,(5,0,0),(10,0,0)),101.25)
    out=f.fuse(None,101.35)
    assert out['pitch']==pytest.approx(1)

def test_single_fused_pose_prevents_duplicate_gestures():
    f=calibrated();g=GestureRecognizer();g.calibrate(pose())
    emitted=[]
    for i in range(40):
        t=1.25+i*.05;f.ingest(sample(t,(25,0,0)),100+t)
        fused=f.fuse(pose(20),100+t)
        with patch('vision.gestures.time.monotonic',return_value=100+t):event=g.process(fused)
        if event:emitted.append(event)
    assert len(emitted)==1

def test_missing_protocol_never_opens_a_serial_port(monkeypatch):
    monkeypatch.setenv('CONTEXTSWITCH_IMU_DECODER','')
    monkeypatch.setenv('CONTEXTSWITCH_IMU_PORT','test-only-port')
    device=SerialIMU(PoseFusion());device.start()
    assert device.thread is None and device.status=='UNAVAILABLE'

def test_hand_scroll_arming_motion_and_pinch_conflict():
    s=HandScroll();hand={'detected':True,'scroll_pose':True,'pinching':False,'index_y':.4}
    assert s.process(hand,0)[0][0]=='PINCH_CANCEL'
    assert s.process(hand,.1)==[]
    result=s.process({**hand,'index_y':.5},.3)
    assert result[0][0]=='SCROLL' and result[0][1]['delta_y']>0
    assert s.process({**hand,'pinching':True},.4)==[]
    assert s.last_y is None

def test_context_calibrates_and_honors_hands_occupied():
    now=[0.];a=ContextShift(clock=lambda:now[0]);a.start('Soldering a board',True)
    for i in range(200):
        now[0]=i*.1;a.observe_visual(True,True);a.observe_audio(100)
    assert a.choose({}, {})=='TYPED'
    now[0]=20.1;a.observe_visual(True,True);a.choose({}, {})
    now[0]=21.7;a.observe_visual(True,True)
    assert a.choose({}, {})=='HEAD'
    assert a.noise_limit==200
    assert a.choose({}, {'text_entry':True})=='TYPED'

def test_context_visual_loss_falls_back_and_no_auto_without_optin():
    now=[0.];a=ContextShift(clock=lambda:now[0])
    assert a.choose({}, {}) is None
    a.start('typing notes')
    now[0]=21
    assert a.choose({}, {})=='TYPED'


def test_actual_pico_csv_units_order_and_calibration_status():
    d=Decoder()
    assert d.parse('1000,0,0,1,0,0,0') is None
    d.parse('# STATUS,ready=1,calibrated=1,packets=123')
    for i in range(12):s=d.parse(f'{1020+i*20},0,0,1,0,0,10')
    assert s.device_time==pytest.approx(1.24)
    assert s.gyro==(0,10,0)
    assert s.angles[1]>2
    assert s.confidence==.9
    d.parse('# CALIBRATION_START')
    assert not d.ready and d.reset_required
    assert d.parse('2000,0,0,1,0,0,0') is None
    d.parse('# CALIBRATION_DONE');assert d.ready


def test_pico_errors_reset_and_malformed_packets_are_rejected():
    d=Decoder();d.parse('# CALIBRATION_DONE')
    with pytest.raises(ValueError):d.parse('1,2,3')
    with pytest.raises(ValueError):d.parse('# ERROR_IMU_READ')
    with pytest.raises(ValueError):d.parse('10,nan,0,1,0,0,0')


def test_pico_split_packet_and_millisecond_wrap():
    d=Decoder();d.ready=True
    class Stream:
        def __init__(self):self.chunks=iter([b'4294967280,0,',b'0,1,0,0,0\n',b'4,0,0,1,0,0,0\n'])
        def read_until(self,*args,**kwargs):return next(self.chunks)
    stream=Stream()
    assert d(stream) is None
    first=d(stream);second=d(stream)
    assert second.device_time-first.device_time==pytest.approx(.02)


def test_mounting_basis_is_applied_before_tilt_estimation():
    d=Decoder();d.mount_axes=('-yaw','pitch','roll');d.parse('# CALIBRATION_DONE')
    s=d.parse('1000,0,1,0,0,0,0')
    assert s.mounted and s.angles==(0.,0.,0.)


def test_stale_camera_frame_does_not_anchor_fusion():
    f=PoseFusion();out=f.fuse({**pose(),'timestamp_monotonic':99},100)
    assert not out['valid_for_actions']
