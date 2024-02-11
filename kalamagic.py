import pyaudio
from scipy.io import wavfile
import numpy as np
import time
import json
import sys
import os
import keyboard

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

BUFFER = config['bufferLength']
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
        print('Default input rate:', defaultInputRate, ' Default output rate:', defaultOutputRate)
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
    words = line.strip().split(' ')
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

idata = [0]*(BUFFER*2+MAXBUFF)
odata = [0]*MAXBUFF

datas = [idata, odata]
for i in range(TRACKS-2): # Number of buffers
    datas += [[0]*MAXBUFF]

iplayhead = BUFFER + MAXBUFF // 2 # Initial buffer
oplayhead = MAXBUFF//2

framei = 0
totaltime = 0

def identity(a,b):
    global datas, framei
    i = framei
    datas[b][i] = datas[a][i]
    datas[b][i+1] = datas[a][i+1]

def invert(a,b):
    global datas, framei
    i = framei
    datas[b][i] = datas[a][i+1]
    datas[b][i+1] = datas[a][i]

def lowpass(a,b,hz):
    global datas, framei
    i = framei
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

print('Initializing engine ...')

def compute_frame():
    global idata, odata, framei, iplayhead, oplayhead, chain, totaltime

    while len(idata) <= len(odata):
        print('! BUFFER OVERRUN !')
        idata += [0]
    
    if len(odata) > MAXBUFF * 2:
        toRemove = len(odata) - MAXBUFF
        for j in range(TRACKS):
            del datas[j][:toRemove]
        iplayhead -= toRemove // 2
        oplayhead -= toRemove // 2
       
    framei = len(odata)
    odata += [0,0]
    for j in range(2,TRACKS):
        datas[j] += [0,0]

    # Compute output buffer
    for block in chain: # lol
        globals()[block[0]](*block[1])

    # Clipping
    odata[framei] = np.clip(odata[framei], -1, 1)
    odata[framei+1] = np.clip(odata[framei+1], -1, 1)
    
    totaltime += 1/RATE

def icallback(in_data, frame_count, time_info, status):
    global idata,iplayhead
    while len(idata) < 2*iplayhead+2*frame_count:
        idata += [0,0]
    
    samples = [[x / 16384, x / 16384] for x in np.frombuffer(in_data, dtype=np.int16)]
    samples = list(np.array(samples).flatten())
    idata[2*iplayhead:2*iplayhead+2*frame_count] = samples
    iplayhead += frame_count
    
    return(None, pyaudio.paContinue)

def ocallback(in_data, frame_count, time_info, status):
    global odata,oplayhead
    while len(odata) < 2*oplayhead+2*frame_count:
        compute_frame()
    samples = odata[2*oplayhead:2*oplayhead+2*frame_count]
    oplayhead += frame_count
    samplebytes = np.array([s*16384 for s in samples], dtype=np.int16).tobytes()
    return (samplebytes, pyaudio.paContinue)

ostream = p.open(format=pyaudio.paInt16,channels=2,rate=RATE,output=True,stream_callback=ocallback,output_device_index=int(choice2)-1)
istream = p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,stream_callback=icallback,input_device_index=int(choice)-1)

print('Successfully initialized!')

input()

ostream.close()
istream.close()
p.terminate()
