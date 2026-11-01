"""Read the actual V1 firmware without activating browser controls or flashing."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).parents[1]/'backend'))
from pico_imu import Decoder
import serial

parser=argparse.ArgumentParser();parser.add_argument('--port',required=True);parser.add_argument('--baud',type=int,default=115200)
parser.add_argument('--request-status',action='store_true');parser.add_argument('--seconds',type=float,default=12)
args=parser.parse_args();decoder=Decoder();count=0;first=last=None;errors=[];signature=False;received=[]
try:
    with serial.Serial(args.port,args.baud,timeout=.15) as stream:
        if args.request_status:stream.write(b's')
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            line=stream.read_until(b'\n',size=256).decode('ascii',errors='replace').strip()
            if not line:continue
            if line.startswith('#'):
                received.append(line)
                if 'CONTEXTSWITCH_IMU_V1' in line:
                    signature=True;stream.write(b's')
            try:s=decoder.parse(line)
            except ValueError as exc:errors.append(str(exc));continue
            if s:
                count+=1;first=s.device_time if first is None else first;last=s.device_time
        # If a board was already streaming when opened, status is the firmware's
        # documented command. Do not issue it to an unidentified arbitrary device.
except Exception as exc:errors.append(str(exc))
result={'port':args.port,'baud':args.baud,'signature_verified':signature,'decoded_samples':count,
        'sample_rate_hz':None if not first or last==first else round((count-1)/(last-first),1),
        'status_lines':received,'errors':errors,'physical_fusion_verified':False}
(Path(__file__).parents[1]/'IMU_PROBE.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
