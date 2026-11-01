from types import SimpleNamespace
from context_shift import ContextShift
from vision.hand_availability import assess_hands
from execution.manager import ExecutionManager


def hand(extended=True,partial=False):
    points=[SimpleNamespace(x=.5,y=.5) for _ in range(21)]
    for tip in (8,12,16,20):points[tip].y=.3 if extended else .7
    if partial:points[0].x=-.1
    return points


def test_two_full_hands_vs_occupied_and_out_of_frame():
    assert assess_hands([hand(),hand()])['both_hands_visible']
    occupied=assess_hands([hand(False),hand(False)])
    assert occupied['two_hands_possibly_occupied']
    partial=assess_hands([hand(),hand(partial=True)])
    assert partial['incomplete_frame'] and partial['fully_visible_count']==1
    assert not assess_hands([hand()])['both_hands_visible']


def test_fifteen_second_baseline_peak_and_camera_evidence():
    now=[0.];agent=ContextShift(clock=lambda:now[0]);agent.start('Reading a schematic')
    hands=assess_hands([hand(),hand()])
    for i in range(150):
        now[0]=i*.1
        agent.observe_visual(True,True,hands)
        agent.observe_audio(100 if now[0]<5 or now[0]>=10 else 1200,3000)
    assert agent.choose({}, {})=='TYPED'
    now[0]=15.1;agent.observe_visual(True,True,hands);agent.choose({}, {})
    now[0]=16.7;agent.observe_visual(True,True,hands)
    assert agent.choose({}, {})=='HAND'
    state=agent.snapshot()
    assert state['baseline_rms']==100 and state['peak_rms']==1200
    assert state['peak_amplitude']==3000 and state['speech_to_noise_ratio']==12
    assert state['duration_seconds']==15


def test_partial_hands_prefer_head_and_text_focus_overrides():
    now=[0.];a=ContextShift(clock=lambda:now[0]);a.start('Inspecting a board')
    hands=assess_hands([hand(),hand(partial=True)])
    for i in range(170):now[0]=i*.1;a.observe_visual(True,True,hands);a.choose({}, {})
    assert a.current=='HEAD'
    assert a.choose({}, {'text_entry':True})=='TYPED'


def test_revocation_cancels_running_and_queued_actions_without_replay():
    m=ExecutionManager();j=m.submit(7,{'valid':True,'execution_ready':True,'validated_steps':[{'action':'zoom_in'},{'action':'zoom_out'}]})
    m.claim_next(7);m.cancel_tab(7)
    assert m.get_job(j['job_id'])['status']=='CANCELLED'
    assert m.claim_next(7) is None and not m.busy(7)


def test_unavailable_hand_is_suppressed_without_waiting_for_mode_switch():
    import time
    from modality import Arbiter
    a=Arbiter();a.status('CAMERA','TRACKING');a.active='HAND';a.hand_valid=False
    assert not a.allow({'source':'HAND','action':'PINCH_START','timestamp':time.time()*1000})
    assert a.allow({'source':'HAND','action':'TRACKING_LOST'})
