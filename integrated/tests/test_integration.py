import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import integration as system
from execution.manager import ExecutionManager
from modality import Arbiter
from vision.events import EventTranslator, HEAD_ACTIONS
from vision.gestures import GestureRecognizer
from vision.pinch_zoom import PinchZoom


@pytest.fixture
def client():
    system.previews.clear()
    system.store._contexts.clear()
    system.store._active_tab_id = None
    system.execution_manager.queues.clear()
    system.execution_manager.jobs.clear()
    system.execution_manager.in_flight.clear()
    system.execution_manager.deadlines.clear()
    with TestClient(system.app) as c:
        yield c


def context(c,tab=7):
    payload={"tab_id":tab,"url":"https://kicanvas.org/?test=schematic","title":"Test schematic"}
    assert c.post('/context/update',json=payload).status_code==200
    assert c.post(f'/context/activate/{tab}').status_code==200
    return c.get('/context/active').json()


def test_start_without_key_or_hardware(client):
    assert client.get('/health').status_code==200
    s=client.get('/system/state').json()
    assert s['sensors']['IMU']['status']=='UNAVAILABLE'
    assert not s['microphone_verified']
    assert not s['planner_configured']
    assert client.post('/commands/preview',json={'text':'zoom in'}).status_code==409


def test_context_top_level_and_focus(client):
    assert client.post('/context/update',json={'context':{'tab_id':4}}).status_code==400
    context(client)
    client.post('/context/update',json={'tab_id':8,'url':'https://youtube.com/watch?v=a'})
    assert client.get('/context/active').json()['tab_id']==7


def test_typed_plan_approval_dispatch_and_verified_result(client,monkeypatch):
    # The read-only search now needs no approval; emulate a consequential skill
    # here to retain regression coverage of the safety boundary.
    monkeypatch.setattr(system.skill_router.registry['kicanvas'].actions['search_component'],'confirmation',True)
    context(client)
    p=client.post('/commands/preview',json={'text':'find R101'}).json()
    assert p['route']=='DETERMINISTIC'
    assert p['validation']['approval_required']
    assert client.post('/commands/execute',json={'preview_id':p['preview_id']}).status_code==403
    body={'preview_id':p['preview_id'],'approved':True}
    job=client.post('/commands/execute',json=body).json()['job']
    assert client.post('/commands/execute',json=body).json()['job']['job_id']==job['job_id']
    assert client.get('/actions/next?tab_id=8').json()['action'] is None
    a=client.get('/actions/next?tab_id=7').json()['action']
    assert a['target']=='component_search'
    assert client.get('/actions/next?tab_id=7').json()['action'] is None
    result={'action_id':a['action_id'],'tab_id':7,'status':'SUCCESS','verified':True,'result':{'observed_selection':'R101'}}
    assert client.post('/actions/result',json={**result,'tab_id':8}).status_code==400
    assert client.post('/actions/result',json=result).status_code==200
    assert client.post('/actions/result',json=result).status_code==200
    saved=client.get('/actions/jobs/'+job['job_id']).json()
    assert saved['status']=='COMPLETED' and saved['completed_steps']==1


def test_unverified_stops_multistep_and_no_success_lie():
    m=ExecutionManager()
    job=m.submit(1,{'valid':True,'execution_ready':True,'validated_steps':[{'action':'zoom_in'},{'action':'zoom_out'}]})
    a=m.claim_next(1)
    m.record_result(a['action_id'],1,{'status':'SUCCESS','verified':False})
    saved=m.get_job(job['job_id'])
    assert saved['status']=='NEEDS_REVIEW'
    assert saved['results'][0]['status']=='UNVERIFIED'
    assert m.claim_next(1) is None
    assert saved['actions'][1]['status']=='CANCELLED'


def test_timeout_does_not_replay():
    m=ExecutionManager();j=m.submit(1,{'valid':True,'execution_ready':True,'validated_steps':[{'action':'zoom_in'}]})
    m.claim_next(1);m.deadlines[1]=0
    assert m.get_job(j['job_id'])['status']=='FAILED'
    assert m.claim_next(1) is None


def test_clarification_and_missing_key(client):
    context(client)
    p=client.post('/commands/preview',json={'text':'find component'}).json()
    assert p['plan']['needs_clarification']
    assert client.post('/commands/execute',json={'preview_id':p['preview_id'],'approved':True}).status_code==422
    assert client.post('/commands/preview',json={'text':'find R101 and show its details'}).status_code==503


def test_context_change_invalidates_approval(client):
    context(client)
    p=client.post('/commands/preview',json={'text':'find R101'}).json()
    context(client,8)
    assert client.post('/commands/execute',json={'preview_id':p['preview_id'],'approved':True}).status_code==409


def test_invalid_actions_and_dispatch_context(client):
    ctx=context(client)
    body={'tab_id':7,'context':ctx,'plan':{'website':'kicanvas','steps':[{'action':'eval','parameters':{}}]}}
    assert client.post('/actions/validate',json={'plan':body['plan'],'context':ctx}).status_code==422
    body['plan']['steps']=[{'action':'zoom_in','parameters':{}}]
    body['context']={**ctx,'url':'https://evil.example'}
    assert client.post('/actions/dispatch',json=body).status_code==409


@pytest.mark.parametrize('old,new',list(HEAD_ACTIONS.items()))
def test_six_head_mappings(old,new):
    events=EventTranslator().process_head({'valid_for_actions':True},{'action':old})
    assert events[0]['action']==new


@pytest.mark.parametrize('axis,sign,action',[('pitch',-1,'SCROLL_UP'),('pitch',1,'SCROLL_DOWN'),('yaw',-1,'PREVIOUS_PAGE'),('yaw',1,'NEXT_PAGE'),('roll',-1,'ZOOM_OUT'),('roll',1,'ZOOM_IN')])
def test_head_hold_jitter_release(axis,sign,action):
    g=GestureRecognizer();neutral={'valid_for_actions':True,'pitch':0,'yaw':0,'roll':0};g.calibrate(neutral)
    pose={**neutral,axis:sign*20}
    with patch('vision.gestures.time.monotonic',return_value=10): assert g.process(pose) is None
    with patch('vision.gestures.time.monotonic',return_value=10.2): assert g.process(pose)['action']==action
    with patch('vision.gestures.time.monotonic',return_value=11): assert g.process(pose) is None
    assert g.process({'valid_for_actions':False}) is None
    for i in range(10):
        with patch('vision.gestures.time.monotonic',return_value=12+i*.05):g.process(neutral)
    assert g.armed
    for _ in range(10): assert g.process({**neutral,axis:1}) is None


def test_translator_click_debounce_and_loss():
    t=EventTranslator();hand={'detected':True,'index_x':.5,'index_y':.5,'pinching':True}
    with patch('vision.events.time.monotonic',return_value=10):t.process_hand(hand)
    with patch('vision.events.time.monotonic',return_value=10.1):assert any(e['action']=='PINCH_START' for e in t.process_hand(hand))
    # Integration removed legacy release-before-loss; contract cancellation is explicit.
    loss=t.process_hand({'detected':False})
    assert any(e['action']=='TRACKING_LOST' for e in loss)


def test_pinch_zoom_cancels_click_and_releases():
    z=PinchZoom();h={'detected':True,'pinching':True,'pinch_ratio':.1}
    assert z.process(h,0)==[] and z.state=='ARMING'
    assert z.process({**h,'pinch_ratio':.22},.4)[0][0]=='PINCH_CANCEL'
    assert z.state=='ACTIVE'
    assert z.process({**h,'pinch_ratio':.3},.5)[0][0]=='PINCH_ZOOM'
    assert z.process({**h,'pinch_ratio':.9},.6)[0][0]=='PINCH_ZOOM_END'
    assert z.state=='RELEASING'
    z.process({**h,'pinching':False,'pinch_ratio':1},.8)
    assert z.state=='IDLE'
    z.process(h,1);assert z.process(None,1.2)[0][0]=='PINCH_CANCEL'


def test_modality_stale_pause_and_zoom_priority():
    a=Arbiter();a.status('CAMERA','TRACKING')
    def event(source,action):return {'source':source,'action':action,'timestamp':int(time.time()*1000)}
    assert a.allow(event('HAND','PINCH_ZOOM_START'))
    assert not a.allow(event('HEAD','HEAD_TILT_RIGHT'))
    assert not a.allow(event('HEAD','HEAD_DOWN'),busy=True)
    assert a.allow(event('HAND','PINCH_CANCEL'),busy=True)
    assert not a.allow({'source':'HEAD','action':'HEAD_UP','timestamp':0})
    a.status('CAMERA','PAUSED');assert not a.allow(event('HAND','PINCH_START'))
    a.status('CAMERA','TRACKING');a.sensors['CAMERA']['timestamp']=1
    assert a.snapshot()['recommended_modality']=='TYPED'
    assert a.active=='HEAD_HAND'


def test_voice_transcript_uses_same_preview_not_mock(client):
    context(client)
    p=system.TranscriptRouter().handle_text('scroll down')
    assert p['source']=='VOICE' and p['plan']['steps'][0]['action']=='pan'
    assert p['job']['status']=='QUEUED'


def test_missing_microphone(client):
    # Explicit mock: hardware capture is not attempted by unit tests.
    with patch.dict('sys.modules',{'speech_recognition':None}):
        data=client.post('/voice/listen',json={}).json()
    assert data['voice_event']['status']=='UNAVAILABLE'
    assert client.get('/system/state').json()['microphone_verified'] is False


def test_pause_heartbeat_and_ws_reconnect(client):
    assert client.post('/system/camera',json={'paused':True}).status_code==200
    for _ in range(2):
        with client.websocket_connect('/ws/cv') as ws:
            data=ws.receive_json()
            assert data['type']=='SENSOR_STATUS' and data['status']=='PAUSED'
            ws.send_text('heartbeat')


def test_untrusted_website_cannot_send_approval(client):
    response=client.post('/commands/execute',headers={'Origin':'https://evil.example'},json={'preview_id':'x','approved':True})
    assert response.status_code==403


def test_contextual_planner_adapter_with_mock_model(client,monkeypatch):
    # Mock planner output; this verifies routing/validation, not a live Gemini call.
    context(client)
    monkeypatch.setenv('GEMINI_API_KEY','test-only-not-a-real-key')
    seen=[]
    def fake(request):
        seen.append(request)
        return {'website':'kicanvas','intent':request.command,'steps':[{'action':'zoom_in','parameters':{}}]}
    monkeypatch.setattr(system,'create_plan',fake)
    result=client.post('/commands/preview',json={'text':'magnify the current schematic'}).json()
    assert result['route']=='CONTEXTUAL_AGENT'
    assert seen[0].context['tab_id']==7
    assert result['validation']['execution_ready']


def test_semantic_adapter_requires_confirmation_with_mock_pipeline(client,monkeypatch):
    from types import SimpleNamespace
    context(client)
    monkeypatch.setenv('BEYOND_TOUCH_SEMANTIC','1')
    class Pipeline:
        def decide(self,*args):return SimpleNamespace(action='EXPLAIN_COMPONENT',parameters={'component_ref':'R101'},status='CONFIRM')
    monkeypatch.setattr(system,'semantic_pipeline',Pipeline())
    p=client.post('/commands/preview',json={'text':'tell me more about that part'}).json()
    assert p['route']=='VOICE_SEMANTIC' and not p['validation']['execution_ready']
    assert client.post('/commands/execute',json={'preview_id':p['preview_id']}).status_code==403


def test_worker_camera_failure_is_reported_without_crashing():
    from camera_runtime import CameraRuntime
    a=Arbiter();events=[];runtime=CameraRuntime(events.append,a);runtime.paused=False
    with patch.dict('sys.modules',{'cv2':None}):runtime.run_camera()
    assert a.sensors['CAMERA']['status']=='UNAVAILABLE'
    assert events[-1]['type']=='SENSOR_STATUS'
    assert any(e.get('action')=='TRACKING_LOST' for e in events)
