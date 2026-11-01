"""Native-rate Windows audio capture, with explicit device/host API selection."""
def input_devices():
    import sounddevice as sd
    hosts=sd.query_hostapis()
    default=int(sd.default.device[0])
    devices=[]
    for index, info in enumerate(sd.query_devices()):
        if info['max_input_channels'] < 1: continue
        host=hosts[info['hostapi']]['name']
        try:
            sd.check_input_settings(device=index,channels=1,dtype='int16',samplerate=info['default_samplerate'])
        except Exception: continue
        devices.append({'index':index,'name':info['name'],'host_api':host,'default':index==default,
                        'sample_rate':int(info['default_samplerate'])})
    devices.sort(key=lambda d:(not d['default'], 'WASAPI' not in d['host_api'], d['name']))
    return {'devices':devices,'default_index':default,'capture_backend':'native'}


def capture_fixed(device_index, seconds, phase_callback):
    import sounddevice as sd
    import speech_recognition as sr
    selected=int(sd.default.device[0]) if device_index is None else device_index
    info=sd.query_devices(selected,'input')
    if info['max_input_channels'] < 1: raise ValueError('Selected device is not a microphone input')
    rate=int(info['default_samplerate'])
    sd.check_input_settings(device=selected,channels=1,dtype='int16',samplerate=rate)
    # Open at the device's native rate; forcing 16k on Windows headset drivers
    # is a common source of PortAudio -9999/-9997 failures.
    try:
        audio=sd.rec(int(seconds*rate),samplerate=rate,channels=1,dtype='int16',device=selected,blocking=False)
        if phase_callback: phase_callback('RECORDING',{'seconds':seconds,'device_name':info['name'],'sample_rate':rate})
        sd.wait()
        return sr.AudioData(audio.tobytes(),rate,2)
    finally:
        sd.stop()


def capture_utterance(device_index,seconds,phase_callback):
    """Keep the opening audio; end after speech and a short silence, not a fixed wait."""
    import sounddevice as sd
    import speech_recognition as sr
    import numpy as np
    selected=int(sd.default.device[0]) if device_index is None else device_index
    info=sd.query_devices(selected,'input');rate=int(info['default_samplerate']);block=max(1,rate//20)
    chunks=[];voiced=0;quiet=0;noise=100.
    with sd.InputStream(device=selected,samplerate=rate,channels=1,dtype='int16',blocksize=block) as stream:
        if phase_callback:phase_callback('RECORDING',{'seconds':seconds,'device_name':info['name'],'auto_stop':True})
        for i in range(int(seconds*20)):
            data,overflow=stream.read(block);chunks.append(data.copy())
            rms=float(np.sqrt(np.mean(data.astype(float)**2)))
            if i<3:noise=min(noise,rms) if i else rms
            threshold=max(120,min(600,noise*1.8))
            if rms>threshold:voiced+=1;quiet=0
            else:quiet+=1
            if voiced>=4 and quiet>=10:break
    pcm=np.concatenate(chunks).tobytes() if chunks else b''
    return sr.AudioData(pcm,rate,2)
