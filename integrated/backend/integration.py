"""Single public entry point: uvicorn integration:app --app-dir backend."""
import asyncio
import json
import os
import sys
import time
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parents[1]/".env")
sys.path.insert(0,str(Path(__file__).parent/"voice"))
from main import app, store, skill_router, action_validator, execution_manager, create_plan
from planner.schemas import PlannerRequest
from modality import Arbiter
from camera_runtime import CameraRuntime
from context_shift import ContextShift
from actions import parse_intent

arbiter = Arbiter()
clients = set()
loop = None
queue = None
previews = {}
preview_lock = __import__("threading").Lock()
semantic_pipeline = None
voice_capture = {"phase":"IDLE"}
BUILD = "contextswitch-2026.11.01.8"
auto_shift=ContextShift()
calibration_stop=__import__('threading').Event()
calibration_thread=None


def trusted_origin(origin):
    return not origin or bool(re.fullmatch(r"chrome-extension://[a-p]{32}|http://(?:127\.0\.0\.1|localhost)(?::(?:5173|8001))?", origin))


@app.middleware("http")
async def local_origin(request, call_next):
    if not trusted_origin(request.headers.get("origin")):
        return JSONResponse({"detail":"Origin is not a local UI or installed extension"},status_code=403)
    return await call_next(request)


def publish(event):
    if loop is None or queue is None:
        return
    def put():
        # Never replay a camera backlog after a slow browser or reconnect.
        if queue.full():
            while not queue.empty(): queue.get_nowait()
            queue.put_nowait({"source":"HAND","action":"TRACKING_LOST","timestamp":int(time.time()*1000)})
        queue.put_nowait(event)
    try: loop.call_soon_threadsafe(put)
    except RuntimeError: pass


camera = CameraRuntime(publish,arbiter)
camera.context_shift=auto_shift


async def broadcast():
    while True:
        try:
            event = await asyncio.wait_for(queue.get(),1.5)
        except asyncio.TimeoutError:
            event = {"type":"HEARTBEAT","timestamp":int(time.time()*1000)}
        desired=auto_shift.choose(arbiter.sensors,store.get_active())
        if desired and desired!=arbiter.active:
            arbiter.active=desired;camera.cancel()
        if event.get("source") in ("HEAD","HAND"):
            tab = store.get_active().get("tab_id")
            busy = execution_manager.busy(tab)
            if not arbiter.allow(event,busy): continue
        for ws in list(clients):
            try: await asyncio.wait_for(ws.send_json(event),.25)
            except Exception: clients.discard(ws)


@asynccontextmanager
async def lifespan(_app):
    global loop, queue
    loop, queue = asyncio.get_running_loop(), asyncio.Queue(maxsize=64)
    camera.stop.clear()
    camera.imu.stop.clear();camera.imu.start()
    camera.start()
    task = asyncio.create_task(broadcast())
    try: yield
    finally:
        await camera.close()
        calibration_stop.set()
        if calibration_thread:await asyncio.to_thread(calibration_thread.join,2)
        await asyncio.to_thread(camera.imu.close)
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        clients.clear()
        loop = queue = None


app.router.lifespan_context = lifespan


@app.websocket("/ws/cv")
async def events(ws: WebSocket):
    if not trusted_origin(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    clients.add(ws)
    try:
        await ws.send_json({"type":"SENSOR_STATUS","sensor":"CAMERA",**arbiter.sensors["CAMERA"]})
        while True: await ws.receive_text()  # heartbeat only, never execute incoming browser events
    except WebSocketDisconnect: pass
    finally: clients.discard(ws)


@app.get("/system/state")
def system_state():
    return {**arbiter.snapshot(), "camera_detail":camera.detail,
            "build":BUILD,"browser_connected":bool(clients),
            "head":camera.head_state,"voice_capture":voice_capture,
            "camera_performance":camera.performance,
            "context_shift":auto_shift.snapshot(),"fusion":camera.fusion.snapshot(),
            "recommendation_only":not auto_shift.enabled,
            "imu":{"status":camera.imu.status,"detail":camera.imu.detail,"port":camera.imu.port or None},
            "context":store.get_active(),"planner_configured":bool(os.getenv("GEMINI_API_KEY")),
            "microphone_verified":arbiter.sensors["MICROPHONE"]["status"] == "AVAILABLE"}


class CameraControl(BaseModel):
    paused: bool


@app.post("/system/camera")
async def camera_control(control: CameraControl):
    camera.paused = control.paused
    if control.paused:arbiter.head_valid=False
    if not control.paused:camera.retry_camera.set()
    camera.cancel()
    camera.status("PAUSED" if control.paused else "RECOVERING")
    if not control.paused and (camera.thread is None or not camera.thread.is_alive()): camera.start()
    return system_state()


class Mode(BaseModel):
    modality: str


@app.post("/system/head/recenter")
def recenter_head():
    camera.recenter_at=time.monotonic()+2
    camera.recenter.set()
    camera.head_state={'state':'CALIBRATING','calibrated':False,'delta':{},'calibration_progress':0}
    camera.cancel()
    return {"status":"CALIBRATING","instruction":"Look straight ahead and hold still"}


@app.get('/system/camera/preview')
def camera_preview():
    fresh=camera.preview is not None and time.monotonic()-camera.preview_time<1
    return {'image':camera.preview if fresh else None,'format':'jpeg','live':fresh}


@app.post("/system/modality")
def select_mode(body: Mode):
    if body.modality=='AUTO':
        if not auto_shift.finished:raise HTTPException(409,'Run the 15-second calibration first, then enable automatic switching.')
        auto_shift.enabled=True;auto_shift.current='TYPED';auto_shift.candidate=None
        arbiter.active='TYPED';camera.cancel()
        return system_state()
    if body.modality not in ("HEAD_HAND","HEAD","HAND","TYPED","VOICE"):
        raise HTTPException(422,"Unknown modality")
    arbiter.active = body.modality
    auto_shift.enabled=False
    calibration_stop.set()
    camera.cancel()
    return system_state()


class Command(BaseModel):
    text: str = Field(min_length=1,max_length=2000)
    source: str = "TYPED"


def deterministic(text,context):
    kind,name,params = parse_intent(text)
    # Do not use the source parser's greedy single-command pattern on multi-step commands.
    if " and " in text.lower(): return None
    translations = {"LOCATE_COMPONENT":("search_component",{"query":params.get("component_ref")}),
                    "EXPLAIN_COMPONENT":("view_component_details",{"reference":params.get("component_ref")}),
                    "SCROLL_UP":("pan",{"direction":"up"}),"SCROLL_DOWN":("pan",{"direction":"down"})}
    if kind == "ambiguous" or text.lower().strip() in ("find component","find","show details"):
        return {"website":context["website_id"],"intent":text,"needs_clarification":True,
                "clarification_question":"Which component or direction? Please enter the complete command.","steps":[]}
    action = translations.get(name)
    if text.lower().strip() in ("zoom in","zoom out"):
        action = (text.lower().strip().replace(" ","_"),{})
    if action and context["website_id"] == "kicanvas":
        return {"website":"kicanvas","intent":text,"needs_clarification":False,
                "steps":[{"action":action[0],"parameters":action[1]}]}
    return None


@app.post("/commands/preview")
def preview(body: Command):
    context = store.get_active()
    if not context.get("tab_id"):
        raise HTTPException(409,"Activate a supported browser tab with the extension first.")
    plan = deterministic(body.text,context)
    route = "DETERMINISTIC"
    if plan is None:
        # Preserve the supplied semantic resolver/ranker as an opt-in route.
        # Its sample catalog is not assumed to describe the active schematic.
        if os.getenv("BEYOND_TOUCH_SEMANTIC") == "1" and context.get("website_id") == "kicanvas":
            global semantic_pipeline
            if semantic_pipeline is None:
                from pipeline import build_default_pipeline
                semantic_pipeline = build_default_pipeline()
            decision = semantic_pipeline.decide(body.text,"PCB_WEB","KICAD_SCHEMATIC")
            mapped = {"LOCATE_COMPONENT":("search_component","component_ref","query"),
                      "EXPLAIN_COMPONENT":("view_component_details","component_ref","reference")}.get(decision.action)
            if mapped and decision.status in ("ACCEPTED","CONFIRM"):
                action,source_param,dest_param = mapped
                plan={"website":"kicanvas","intent":body.text,"needs_clarification":False,
                      "steps":[{"action":action,"parameters":{dest_param:(decision.parameters or {}).get(source_param)}}]}
                route="VOICE_SEMANTIC"
                force_approval = decision.status == "CONFIRM"
    if plan is None:
        route = "CONTEXTUAL_AGENT"
        if not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(503,"Contextual planner needs backend GEMINI_API_KEY. Try zoom in, scroll down, or find R101.")
        plan = create_plan(PlannerRequest(command=body.text,context=context,page_metadata=context))
        if hasattr(plan,"model_dump"): plan = plan.model_dump(exclude_none=True)
    validation = None if plan.get("needs_clarification") else action_validator.validate_plan(plan,context,False)
    force_approval = locals().get("force_approval",False)
    if validation and force_approval:
        validation.update(approval_required=True,execution_ready=False)
    token = uuid4().hex
    for key,value in list(previews.items()):
        if time.monotonic()-value["created"] > 300: previews.pop(key,None)
    previews[token] = {"plan":plan,"context":dict(context),"created":time.monotonic(),"job":None,"force_approval":force_approval}
    return {"preview_id":token,"transcript":body.text,"source":body.source,"route":route,"plan":plan,"validation":validation}


class Execute(BaseModel):
    preview_id: str
    approved: bool = False


@app.post("/commands/execute")
def execute(body: Execute):
    with preview_lock:
        return execute_once(body)


def execute_once(body: Execute):
    item = previews.get(body.preview_id)
    if not item: raise HTTPException(404,"Preview expired or backend restarted")
    if item["job"]: return {"job":execution_manager.get_job(item["job"])}
    context = store.get_active()
    if time.monotonic()-item["created"] > 120 or any(context.get(k) != item["context"].get(k) for k in ("tab_id","url")):
        raise HTTPException(409,"Context changed or preview expired; preview again")
    if item["plan"].get("needs_clarification"): raise HTTPException(422,"Clarification required")
    if item.get("force_approval") and not body.approved: raise HTTPException(403,"Semantic suggestion requires explicit approval")
    result = action_validator.validate_plan(item["plan"],item["context"],body.approved)
    if not result.get("execution_ready"): raise HTTPException(403,"Explicit approval required")
    job = execution_manager.submit(context["tab_id"],result)
    item["job"] = job["job_id"]
    camera.cancel()
    publish({'type':'ACTION_READY','tab_id':context['tab_id']})
    return {"job":job}


class TranscriptRouter:
    """ASR uses the original recognizer; no MockExecutor can be reached."""
    def handle_text(self,text,*args,**kwargs):
        try:
            planned=preview(Command(text=text,source="VOICE"))
            if planned['plan'].get('needs_clarification'):return planned
            if not planned.get('validation',{}).get('execution_ready'):return planned
            return {**planned,**execute(Execute(preview_id=planned['preview_id']))}
        except HTTPException as exc:
            return {"status":"PLANNING_FAILED","message":exc.detail,"transcript":text}


audio_lock = __import__("threading").Lock()


class AutoCalibration(BaseModel):
    pre_context: str = Field(min_length=1,max_length=2000)
    hands_occupied: bool = False
    device_index: int | None = Field(default=None,ge=0)


class BrowserRevoke(BaseModel):
    tab_ids: list[int] = Field(default_factory=list,max_length=1000)


@app.post('/system/browser/revoke')
def revoke_browser(body: BrowserRevoke):
    for tab_id in body.tab_ids:
        execution_manager.cancel_tab(tab_id);store.remove(tab_id)
        for token,item in list(previews.items()):
            if item['context'].get('tab_id')==tab_id:previews.pop(token,None)
    camera.cancel()
    return {'revoked_tabs':body.tab_ids,'status':'CANCELLED'}


class IMUConnection(BaseModel):
    port: str = Field(default='',max_length=128)
    baud: int = Field(default=115200,ge=1200,le=2000000)
    axes: list[str] = Field(default_factory=lambda:['pitch','yaw','roll'],min_length=3,max_length=3)


@app.post('/hardware/connect')
def connect_imu(body: IMUConnection):
    from motion import PoseFusion
    try:PoseFusion(tuple(body.axes))
    except ValueError as exc:raise HTTPException(422,str(exc))
    if body.port:
        from serial.tools import list_ports
        if body.port not in [p.device for p in list_ports.comports()]:raise HTTPException(422,'Select a currently enumerated serial port')
    camera.imu.close()
    if camera.imu.thread and camera.imu.thread.is_alive():raise HTTPException(409,'Previous serial reader is still closing')
    camera.fusion.disconnect();camera.fusion.mapping=tuple(body.axes)
    camera.imu.port=body.port;camera.imu.baud=body.baud;camera.imu.status='UNAVAILABLE'
    camera.imu.detail='Serial input disabled' if not body.port else 'Connecting to firmware V1'
    camera.imu.stop.clear();camera.imu.start();camera.recenter.set();camera.cancel()
    return system_state()


@app.post('/system/context-shift/calibrate')
def calibrate_context(body: AutoCalibration):
    global calibration_thread
    if calibration_thread and calibration_thread.is_alive():raise HTTPException(409,'Calibration is already running')
    calibration_stop.clear();auto_shift.start(body.pre_context,body.hands_occupied)
    if camera.paused:
        camera.paused=False;camera.retry_camera.set();camera.status('RECOVERING')
        if not camera.thread or not camera.thread.is_alive():camera.start()
    camera.recenter.set();camera.cancel()
    arbiter.active='TYPED'
    def sample_audio():
        selected=body.device_index if body.device_index is not None else int(os.environ['BEYOND_TOUCH_MIC_INDEX']) if os.getenv('BEYOND_TOUCH_MIC_INDEX') else None
        auto_shift.sample_microphone(selected,audio_lock,calibration_stop)
        if auto_shift.audio:arbiter.status('MICROPHONE','AVAILABLE')
    calibration_thread=__import__('threading').Thread(target=sample_audio,daemon=True)
    calibration_thread.start()
    return auto_shift.snapshot()


@app.post('/system/context-shift/stop')
def stop_context_shift():
    auto_shift.enabled=False;calibration_stop.set();camera.cancel()
    return auto_shift.snapshot()


@app.get('/hardware/ports')
def serial_ports():
    try:
        from serial.tools import list_ports
        return {'ports':[{'port':p.device,'description':p.description} for p in list_ports.comports()],
                'decoder_required':not bool(camera.imu.decoder)}
    except ImportError:return {'ports':[],'error':'Optional pyserial is not installed','decoder_required':True}


@app.post('/hardware/calibrate')
def calibrate_imu():
    if not camera.imu.port:raise HTTPException(409,'Set CONTEXTSWITCH_IMU_PORT to an available serial port first')
    camera.imu.calibrate.set();camera.recenter.set();camera.cancel()
    return {'status':'RECOVERING','instruction':'Keep the mounted sensor and your head still for firmware calibration (~6 seconds), then webcam alignment.'}


@app.get("/voice/devices")
def voice_devices():
    try:
        from audio_capture import input_devices
        return input_devices()
    except Exception as exc:
        return {"devices":[],"error":str(exc)}


class VoiceCapture(BaseModel):
    device_index: int | None = Field(default=None,ge=0)
    language: str = Field(default="en-US",pattern=r"^en-(US|IN|GB|AU)$")
    seconds: float = Field(default=5,ge=2,le=8)


def voice_phase(phase, detail=None):
    voice_capture.clear()
    voice_capture.update(phase=phase,**(detail or {}))
    # Utterance RMS includes speech and must not be mistaken for ambient noise.


@app.post("/voice/listen")
def listen(body: VoiceCapture = VoiceCapture()):
    if not audio_lock.acquire(blocking=False): raise HTTPException(409,"Capture already running")
    try:
        from voice_input import listen_once
        voice_phase("OPENING_MICROPHONE")
        device=body.device_index if body.device_index is not None else int(os.environ["BEYOND_TOUCH_MIC_INDEX"]) if os.getenv("BEYOND_TOUCH_MIC_INDEX") else None
        result = listen_once("PCB_WEB","KICAD_SCHEMATIC",language=body.language,device_index=device,
                             router=TranscriptRouter(),capture_seconds=body.seconds,phase_callback=voice_phase,capture_backend="native_vad")
        voice_phase("DONE",result.get("audio_diagnostics",{}))
        captured = "audio_diagnostics" in result
        arbiter.status("MICROPHONE","AVAILABLE" if captured else "UNAVAILABLE")
        return result
    except HTTPException: raise
    except Exception as exc:
        voice_phase("ERROR",{"message":str(exc)})
        arbiter.status("MICROPHONE","UNAVAILABLE")
        return {"voice_event":{"status":"UNAVAILABLE"},"error":str(exc),"typed_fallback":True}
    finally: audio_lock.release()


# Backend serves the built React frontend; /docs remains available.
ui = Path(__file__).parents[1]/"frontend/dist"
if ui.is_dir(): app.mount("/",StaticFiles(directory=ui,html=True),name="frontend")
