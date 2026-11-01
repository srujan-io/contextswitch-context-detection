from types import SimpleNamespace
from context_shift import ContextShift
from vision.hand_render import draw_hands


def ready_agent():
    now=[0.];agent=ContextShift(clock=lambda:now[0]);agent.start('Reading a schematic')
    for i in range(150):
        now[0]=i*.1
        agent.observe_audio(100 if i<50 or i>=100 else 1200,3000)
    now[0]=15.1
    return agent,now,{'MICROPHONE':{'status':'AVAILABLE'}}


def hands(full=True):
    return {'both_hands_visible':full,'two_hands_possibly_occupied':False,'hand_count':2 if full else 0,'fully_visible_count':2 if full else 0}


def test_voice_to_two_hands_and_immediate_loss_back_to_voice():
    a,now,sensors=ready_agent()
    a.observe_visual(True,False,hands(False));a.choose(sensors,{})
    now[0]=16.7;a.observe_visual(True,False,hands(False))
    assert a.choose(sensors,{})=='VOICE'
    for i in range(30):
        now[0]=17+i*.05;a.observe_visual(True,True,hands());a.choose(sensors,{})
    assert a.current=='HAND'
    now[0]+=.05;a.observe_visual(True,False,hands(False))
    assert a.choose(sensors,{})=='VOICE'  # no stale 2-second hand window/dwell delay


def test_idle_voice_profile_does_not_expire_while_hands_control_page():
    a,now,sensors=ready_agent();now[0]=90
    a.observe_visual(False,False,hands(False));a.choose(sensors,{})
    now[0]=92;a.observe_visual(False,False,hands(False))
    assert a.choose(sensors,{})=='VOICE'
    assert a.snapshot()['voice_recording']=='on request only'


def test_unavailable_microphone_falls_back_to_head_then_typed():
    a,now,_=ready_agent();sensors={'MICROPHONE':{'status':'UNAVAILABLE'}}
    for i in range(40):now[0]=16+i*.05;a.observe_visual(True,False,hands(False));a.choose(sensors,{})
    assert a.current=='HEAD'
    now[0]=25;a.observe_visual(False,False,hands(False));assert a.choose(sensors,{})=='TYPED'


def test_two_hands_are_rendered_with_distinct_labels_and_one_pointer():
    labels=[];circles=[]
    cv=SimpleNamespace(FONT_HERSHEY_SIMPLEX=0,LINE_AA=0,line=lambda *args:None,circle=lambda *args:circles.append(args),putText=lambda frame,text,*args:labels.append(text))
    points=[SimpleNamespace(x=.5,y=.5) for _ in range(21)]
    draw_hands(SimpleNamespace(shape=(480,640,3)),[points,points],['Left','Right'],0,{'hands':[{'fully_visible':True},{'fully_visible':True}],'fully_visible_count':2},[(0,1)],cv)
    assert len(circles)==42
    assert 'Left / pointer' in labels and 'Right' in labels
    assert any('Hands: 2/2' in label for label in labels)
