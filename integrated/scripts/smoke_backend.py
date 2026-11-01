"""Real HTTP server start/restart smoke test, no hardware or Gemini calls."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

root=Path(__file__).parents[1]
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
def request(path,body=None):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=3) as r:return json.load(r)
env={**os.environ,'BEYOND_TOUCH_CAMERA':'0'}
job_id=None
for cycle in range(2):
    with (root/'smoke-server.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','integration:app','--app-dir',str(root/'backend'),'--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log)
        try:
            for _ in range(60):
                try:request('/health');break
                except Exception:
                    if proc.poll() is not None:raise RuntimeError((root/'smoke-server.log').read_text())
                    time.sleep(.1)
            else:raise RuntimeError('Startup timed out')
            assert request('/system/state')['sensors']['IMU']['status']=='UNAVAILABLE'
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/') as page:assert b'ContextSwitch' in page.read()
            if cycle==0:
                request('/context/update',{'tab_id':7,'url':'https://kicanvas.org/'})
                request('/context/activate/7',{})
                p=request('/commands/preview',{'text':'zoom in'})
                job_id=request('/commands/execute',{'preview_id':p['preview_id']})['job']['job_id']
                a=request('/actions/next?tab_id=7')['action']
                request('/actions/result',{'action_id':a['action_id'],'tab_id':7,'status':'UNVERIFIED','verified':False})
                assert request('/actions/jobs/'+job_id)['status']=='NEEDS_REVIEW'
            else:
                try:request('/actions/jobs/'+job_id)
                except urllib.error.HTTPError as e:assert e.code==404
                else:raise AssertionError('Old job unexpectedly survived process restart')
                assert request('/actions/next?tab_id=7')['action'] is None
        finally:
            proc.terminate();proc.wait(timeout=8)
print('PASS: real HTTP startup, UI serving, typed preview, dispatch, unverified result, restart with no stale replay')
