import pyaudio
from scipy.io import wavfile
import numpy as np
import time
import json
import sys
import os
import keyboard
import traceback

print('Loading configuration ...')

config = None
if not os.path.isfile('config.json'):
    fp = open('defaults.json', 'r')
    config = json.load(fp)
    fp.close()
else:
    fp = open('config.json', 'r')
    config = json.load(fp)
    fp.close()

# gets passed to p.open as is, ie increase if it's performing bad
# the number of frames (samples) that get passed to the input and output callbacks at a time
# 0 defaults to whatever the system wants, 1024 on mine
PACKET = config['packetLength']
# processed sections will always be a multiple of this
BUFFER = config['bufferLength']
# the number of frames that get stored from the past
MAXBUFF = config['historyLength']
RATE = config['sampleRate']

terminate = False

print('Loading devices ...')

p=pyaudio.PyAudio()
numdevices = p.get_device_count()

def getDeviceFullName(i):
    return p.get_host_api_info_by_index(p.get_device_info_by_index(i).get('hostApi')).get('name') + ' - ' + p.get_device_info_by_index(i).get('name')

choice = 'blah'

for i in range(0, numdevices):
    if (p.get_device_info_by_index(i).get('maxInputChannels')) > 0:
        if getDeviceFullName(i) == config['inputDevice']:
            choice = str(i+1)

if not choice.isdigit():
    print('')
    print('Input device "' + config['inputDevice'] + '" not found, please select one:')
    for i in range(0, numdevices):
        if (p.get_device_info_by_index(i).get('maxInputChannels')) > 0:
            print(str(i+1) + ".", getDeviceFullName(i))
            
    print('')
    while not choice.isdigit() or int(choice) <= 0 or int(choice) > numdevices:
        choice = input('Enter an audio device number or 0 to exit: ')
        if choice == '0':
            terminate = True
            break
    print('')

if terminate:
    sys.exit(0)

choice2 = 'blah'

for i in range(0, numdevices):
    if (p.get_device_info_by_index(i).get('maxOutputChannels')) > 0:
        if getDeviceFullName(i) == config['outputDevice']:
            choice2 = str(i+1)

if not choice2.isdigit():
    print('')
    print('Output device "' + config['outputDevice'] + '" not found, please select one:')
    for i in range(0, numdevices):
        if (p.get_device_info_by_index(i).get('maxOutputChannels')) > 0:
            print(str(i+1) + ".", getDeviceFullName(i))
            
    print('')
    while not choice2.isdigit() or int(choice2) <= 0 or int(choice2) > numdevices:
        choice2 = input('Enter an audio device number or 0 to exit: ')
        if choice2 == '0':
            terminate = True
            break
    print('')

if terminate:
    sys.exit(0)

if RATE < 0:
    defaultInputRate = p.get_device_info_by_index(int(choice)-1).get('defaultSampleRate')
    defaultOutputRate = p.get_device_info_by_index(int(choice2)-1).get('defaultSampleRate')
    if defaultOutputRate == defaultInputRate:
        RATE = int(defaultOutputRate)
        print('User did not specify a custom sample rate, using default rate of', RATE)
    else:
        print('Default input/output sample rates did not match and user did not set a custom one!')
        print('Default input rate:', defaultInputRate, 'Default output rate:', defaultOutputRate)
        sys.exit(0)

config['inputDevice'] = getDeviceFullName(int(choice)-1)
config['outputDevice'] = getDeviceFullName(int(choice2)-1)

print('Saving configuration ...')

fp = open('config.json', 'w')
json.dump(config, fp, indent=4)
fp.close()

print('')
print('Choose a filter file:')

filelist = os.listdir('filters')
for i in range(len(filelist)):
    print(str(i+1) + ".", filelist[i])

choice3 = 'blah'
print('')
while not choice3.isdigit() or int(choice3) <= 0 or int(choice3) > len(filelist):
    choice3 = input('Enter a filter file number or 0 to exit: ')
    if choice3 == '0':
        terminate = True
        break
print('')

if terminate:
    sys.exit(0)

print('Loading filter file ...')

chain = []
maxchannel = 1

wavedata = {}

fp = open('filters/' + filelist[int(choice3)-1], 'r')
for line in fp:
    if line[0] == '#':
        continue
    words = line.strip().split(' ')
    if len(words) == 0:
        continue
    fname = ''
    args = []
    starti = 0
    if len(words) > 1 and words[1] == '->':
        fname = words[3]
        args += [int(words[0]), int(words[2])]
        maxchannel = max(maxchannel, int(words[0]), int(words[2]))
        starti = 4
    elif len(words) > 2 and words[2] == '->':
        fname = words[4]
        args += [int(words[0]), int(words[1]), int(words[3])]
        maxchannel = max(maxchannel, int(words[0]), int(words[1]), int(words[3]))
        starti = 5
    elif len(words) > 3 and words[3] == '->':
        fname = words[5]
        args += [int(words[0]), int(words[1]), int(words[2]), int(words[4])]
        maxchannel = max(maxchannel, int(words[0]), int(words[1]), int(words[2]), int(words[4]))
        starti = 6
    else:
        fname = words[1]
        args += [int(words[0])]
        maxchannel = max(maxchannel, int(words[0]))
        starti = 2
    for i in range(starti, len(words)):
        if words[i].endswith('.wav'):
            wrate, wdata = wavfile.read(words[i])
            wavedata[words[i]] = (wrate, wdata)
        args += [words[i]]
    chain += [(fname, args)]
fp.close()

print('File loaded, ' + str(maxchannel+1) + ' tracks required')

TRACKS = maxchannel + 1

# idata = [0]*(BUFFER*2+MAXBUFF)
# odata = [0]*MAXBUFF

# buffer[track (input, output, intermediate tracks), frame num, channel (left/right)]
buffer = np.zeros((TRACKS, MAXBUFF*2, 2))
# datas = [idata, odata]
# for i in range(TRACKS-2): # Number of buffers
#     datas += [[0]*MAXBUFF]

auxdata = [None]*TRACKS

# iplayhead = BUFFER + MAXBUFF // 2 # Initial buffer
# oplayhead = MAXBUFF//2

# framei = 0
# totaltime = 0
# section start: start frame index of what needs to be processed / was last processed
sec_st = MAXBUFF
# section end: end frame index (ie one past the last one) to be processed
# sectionEnd - sectionStart == the length of frames that need to be produced
sec_end = MAXBUFF
output_head = MAXBUFF
input_head = MAXBUFF
# start and end times overall of current section
start_time = 0.0
end_time = 0.0

def identity(a,b):
    buffer[b,sec_st:sec_end] = buffer[a,sec_st:sec_end]

def invert(a,b):
    buffer[b,sec_st:sec_end,0] = buffer[a,sec_st,sec_end,1]
    buffer[b,sec_st:sec_end,1] = buffer[a,sec_st,sec_end,0]

def lowpass(a,b,hz):
    t = np.tan(np.pi * float(hz) / RATE)
    datas[b][i] = (t * datas[a][i] + t * datas[a][i-2] + (1-t) * datas[b][i-2]) / (t+1)
    datas[b][i+1] = (t * datas[a][i+1] + t * datas[a][i-1] + (1-t) * datas[b][i-1]) / (t+1)

def basichighpass(a,b):
    global datas, framei
    i = framei
    datas[b][i] = (datas[a][i] - datas[a][i-2]) / (2)
    datas[b][i+1] = (datas[a][i+1] - datas[a][i-1]) / (2)

def amplify(a,b,db):
    global datas, framei
    i = framei
    fac = np.power(10,float(db)/10)
    datas[b][i] = datas[a][i] * fac
    datas[b][i+1] = datas[a][i+1] * fac

def tanhlimit(a,b):
    global datas, framei
    i = framei
    datas[b][i] = np.tanh(datas[a][i])
    datas[b][i+1] = np.tanh(datas[a][i+1])

def delay(a,b,ms,t):
    global datas, framei
    i = framei
    d = int((float(ms) * RATE) // 1000)
    t = float(t)
    datas[b][i] = datas[a][i] * (1-t) + datas[b][i-2*d] * t
    datas[b][i+1] = datas[a][i+1] * (1-t) + datas[b][i+1-2*d] * t

def delayinvert(a,b,ms,t):
    global datas, framei
    i = framei
    d = int((float(ms) * RATE) // 1000)
    t = float(t)
    datas[b][i] = datas[a][i] * (1-t) + datas[b][i+1-2*d] * t
    datas[b][i+1] = datas[a][i+1] * (1-t) + datas[b][i-2*d] * t
    
def mix(a,b,c,t):
    global datas, framei
    i = framei
    t = float(t)
    datas[c][i] = datas[a][i] * (1-t) + datas[b][i] * t
    datas[c][i+1] = datas[a][i+1] * (1-t) + datas[b][i+1] * t
    
def pitchshift(a,b,pitch,cutoff=172):
    global datas, framei
    i = framei
    
    pitch = float(pitch)
    cutoff = float(cutoff)
    
    cutoffLen = int(RATE / cutoff / 2) * 2
    
    imod = i % cutoffLen
    chunki = i - imod
    pchunki = chunki - cutoffLen

    pcind1 = int(imod * pitch / 2) * 2
    pcind2 = int((imod * pitch + (1 - pitch) * cutoffLen) / 2) * 2
    
    t = imod / cutoffLen
    
    datas[b][i] = datas[a][pchunki + pcind1] * (1-t) + datas[a][pchunki + pcind2] * t
    datas[b][i+1] = datas[a][pchunki + pcind1 + 1] * (1-t) + datas[a][pchunki + pcind2 + 1] * t

def rectify(a,b):
    global datas, framei
    i = framei
    datas[b][i] = abs(datas[a][i])
    datas[b][i+1] = abs(datas[a][i+1])

def sine(a, hz):
    global datas, framei, totaltime
    i = framei
    
    hz = float(hz)
    
    datas[a][i] = np.sin(totaltime*hz*2*np.pi)
    datas[a][i+1] = np.sin(totaltime*hz*2*np.pi)

def saw(a, hz):
    global datas, framei, totaltime
    i = framei
    
    hz = float(hz)
    
    datas[a][i] = -1 + 2*hz*(totaltime % (1/hz))
    datas[a][i+1] = -1 + 2*hz*(totaltime % (1/hz))

def square(a, hz, duty=0.5):
    global datas, framei, totaltime
    i = framei
    
    hz = float(hz)
    duty = float(duty)
    
    p = 1
    if hz*(totaltime % (1/hz)) > duty:
        p = -1
    
    datas[a][i] = p
    datas[a][i+1] = p

def triangle(a, hz):
    global datas, framei, totaltime
    i = framei
    
    hz = float(hz)
    
    datas[a][i] = abs((totaltime % (1/hz)) - 1/(2*hz)) * hz - 1
    datas[a][i+1] = abs((totaltime % (1/hz)) - 1/(2*hz)) * hz - 1

def mult(a,b,c):
    global datas, framei
    i = framei
    datas[c][i] = datas[a][i] * datas[b][i]
    datas[c][i+1] = datas[a][i+1] * datas[b][i+1]

def keypress(a, key):
    global datas, framei
    i = framei
    
    if i % 1024 == 0:
        datas[a][i] = 2*int(keyboard.is_pressed(key))-1
        datas[a][i+1] = 2*int(keyboard.is_pressed(key))-1
    else:
        datas[a][i] = datas[a][i-2]
        datas[a][i+1] = datas[a][i-1]

def modmix(a,b,c,d):
    global datas, framei
    i = framei
    datas[d][i] = datas[a][i] * (0.5 - 0.5*datas[c][i]) + datas[b][i] * (0.5 + 0.5*datas[c][i])
    datas[d][i+1] = datas[a][i+1] * (0.5 - 0.5*datas[c][i+1]) + datas[b][i+1] * (0.5 + 0.5*datas[c][i+1])

def wavfile(a, fname):
    global datas, framei, totaltime, wavedata
    i = framei
    
    wrate = wavedata[fname][0]
    wdata = wavedata[fname][1]
    sampleno = round(totaltime * wrate)
    totalsamps = len(wdata)
    sampleno = sampleno % totalsamps
    l = wdata[sampleno][0]
    r = wdata[sampleno][1]
    
    datas[a][i] = l / 32768
    datas[a][i+1] = r / 32768

def pan(a,b,pan):
    global datas, framei
    i = framei
    
    theta = float(pan) * (np.pi/4) + (np.pi/4)
    
    datas[b][i] = np.cos(theta)*datas[a][i]
    datas[b][i+1] = np.sin(theta)*datas[a][i+1]

def modpan(a,b,c):
    global datas, framei
    i = framei
    
    theta = (datas[b][i] + datas[b][i+1]) / 2 * (np.pi/4) + (np.pi/4)
    
    datas[c][i] = np.cos(theta)*datas[a][i]
    datas[c][i+1] = np.sin(theta)*datas[a][i+1]

def gate(a,b,db,msrelease):
    global datas, framei, totaltime, auxdata
    i = framei
    
    fac = np.power(10,float(db)/10)
    
    if auxdata[b] is None:
        auxdata[b] = totaltime
    
    if abs((datas[a][i] + datas[a][i+1]) / 2) > fac:
        auxdata[b] = totaltime
    
    multiplier = max(0, 1 - (totaltime - auxdata[b]) / (float(msrelease) / 1000))
    
    datas[b][i] = datas[a][i] * multiplier
    datas[b][i+1] = datas[a][i+1] * multiplier

print('Initializing engine ...')

def icallback(in_data, frame_count, time_info, status):
    global sec_st, sec_end, output_head, input_head, start_time, end_time
    try:
        input_len = frame_count
        if input_len > MAXBUFF:
            input_len = MAXBUFF
            print('Input buffer overrun!')
        input_end = input_head + input_len
        if input_end > MAXBUFF*2:
            # shift everything from second half to first half
            # in theory we could instead keep two buffers and swap between them, but eh
            buffer[:,:MAXBUFF] = buffer[:,MAXBUFF:]
            sec_st = max(0, sec_st-MAXBUFF)
            sec_end = max(0, sec_end-MAXBUFF)
            output_head -= MAXBUFF
            if output_head < 0:
                output_head = 0
                print('Output buffer overrun!')
            input_head -= MAXBUFF
            input_end -= MAXBUFF
        # take last input_len samples
        input_array = np.frombuffer(in_data, dtype=np.int16)[-input_len:]
        input_array = input_array.astype(np.float64) / 16384
        buffer[0,input_head:input_end,0] = input_array
        buffer[0,input_head:input_end,1] = input_array
        input_head = input_end

        if input_head > sec_end+BUFFER:
            start_time += (sec_end-sec_st) / RATE
            sec_st = sec_end
            # ensure amount to process is always a multiple of BUFFER
            sec_end = (input_head-sec_st)//BUFFER * BUFFER + sec_st
            end_time += (sec_end-sec_st) / RATE
            # print('Processing', (start_time, end_time))
            print('Processing', (sec_st, sec_end))
            for block in chain: # lol, lmao even
                globals()[block[0]](*block[1])
            # clipping
            buffer[1,sec_st:sec_end] = np.clip(buffer[1,sec_st:sec_end],-1,1)

        return(None, pyaudio.paContinue)
    except Exception as err:
        # since this runs in a separate thread, errors dont get printed out
        traceback.print_exc()
        raise err

def ocallback(in_data, frame_count, time_info, status):
    try:
        global sec_st, sec_end, output_head
        output_array = np.zeros((frame_count, 2))
        end = min(sec_end, output_head+frame_count)
        output_array[:end-output_head] = buffer[1,output_head:end]
        output_head = end
        # tobytes goes in C order
        # ie frame 0 left, frame 0 right, frame 1 left, frame 1 right
        return ((output_array * 16384).astype(np.int16).tobytes(), pyaudio.paContinue)
    except Exception as err:
        traceback.print_exc()
        raise err

ostream = p.open(format=pyaudio.paInt16,channels=2,rate=RATE,frames_per_buffer=PACKET,
    output=True,stream_callback=ocallback,output_device_index=int(choice2)-1)
istream = p.open(format=pyaudio.paInt16,channels=1,rate=RATE,frames_per_buffer=PACKET,
    input=True,stream_callback=icallback,input_device_index=int(choice)-1)

print('Successfully initialized!')

input()

ostream.close()
istream.close()
p.terminate()
