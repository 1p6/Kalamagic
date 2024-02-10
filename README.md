# Kalamagic

## A FOSS PyAudio-based voice changer

Kalamagic is a realtime voice changer written in Python using the PyAudio library. It does have some other dependencies that are unfortunately pretty heavy (NumPy and SciPy, notably), but mostly they're dependencies that I figure the kind of person who tinkers with Python a lot will already have, and if not, they're easy to install.

The purpose of this project was that I've seen a lot of "free voice changer for streamers" software out there, and most of it either uses AI, is "free" as in "you need to pay us to use 90% of this program but we'll let you use like 2 features for free," or both. My goal here was to create something simple, configurable, and AI-free.

The name is derived from the toki pona word "kalama," meaning "sound," and the English word "magic."

### Quickstart Guide

If you just want to quickly get your voice changed, here's how:

1. Install [Python 3](https://www.python.org/) if you don't already have it. (Sorry, I have no idea what the minimum version is, but anything vaguely up-to-date should work.)
2. Opening a command line as administrator, run the following commands:
	- `python -m pip install numpy`
	- `python -m pip install scipy`
	- `python -m pip install pyaudio`
	- `python -m pip install keyboard`
	The first two of these will probably take the longest (if you do not already have them installed).
3. Clone this repository. There's no need to build anything; it's Python.
4. Opening a command line, navigate to the repository directory and run `python kalamagic.py`.
5. You will first be prompted to select an input device from a list. This should be your microphone or whatever you want to use to feed audio to the program. When in doubt, open another audio program (e.g. Discord) and check what it's set to use.
	(NOTE: you'll probably see each device appear several times with different prefixes; for example, my microphone shows up once as MME, once as Windows DirectSound, once as Windows WASAPI, and once as Windows WDM-KS. These represent different interfaces to access the same device; ideally they will all work, but in practice you may want to try different ones to see if the performance is better or worse.)
6. You will next be prompted to select an output device from a list. For now, select your speakers/headphones.
7. Lastly, you will be asked to choose a filter from a list. Pick whichever one you like (I recommend blackhelmet.txt).
8. You should be able to hear yourself now! You can press any key afterwards to close the program.

### How do I use it for Discord, OBS, etc.?

Kalamagic can only output to an audio *output* device, so you need some way to feed that output into an *input* device. There are many ways to do this, from advanced software packages to the old "plug the line out into the line in" trick. One easy way on Windows is [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).

### Configuration

The config.json file contains five fields that control how Kalamagic runs:

* `inputDevice`: This is the name of the audio input device. If this device is not found, you will be prompted to select one, and the configuration file will be updated. So to change your device, simply replace the name with an empty string.
* `outputDevice`: This is the name of the audio output device. As with the input device, you will be prompted if this does not exist, and the configuration file will be updated.
* `bufferLength`: This is how long the *buffer* is, i.e. how much audio the program will work with at a time. It takes time to do the audio computations, so if this length is too low, you will see `! BUFFER OVERRUN !` in the console, and the audio will sound distorted. If this happens, increase the setting and restart the program.
* `historyLength`: This is how much previous audio Kalamagic keeps track of. If this value is too short, some audio effects will sound distorted, but the program's RAM usage will be proportional to this value.
* `sampleRate`: This is the sample rate used by the program. You should probably set this to be equal to the sample rate of your microphone, but you can lower it if your CPU isn't fast enough for a given filter.

### Filter Files

Each filter file contains one or more *blocks,* which are individual filters applied to an audio track. A block takes some number of tracks as input and produces one track of output.

A *track* is one complete track of audio (two channels, left and right). Tracks are numbered starting from 0; track 0 is the input, and track 1 is the output. A track should only be used as the output of one block (except for track 0, which should not be used as the output of any block), and tracks should be numbered sequentially (if a filter file uses a track, the program will assume it will also use every lower-numbered track). The more tracks a file uses, the higher the RAM consumption and computational load of the filter.

Below is a list of every possible block:

#### Basic
* `[a] -> [q] identity`: The identity block; this copies track `a` to track `q` without alteration. This is mostly useful for debugging.

#### Volume and Mix
* `[a] -> [q] amplify [db]`: Amplifies track `a` by `db` decibels to produce track `q`. This can be positive or negative.
* `[a] [b] -> [q] mix [t]`: This mixes `a` and `b` to create `q`. The parameter `t` controls the mix; when `t = 0`, `q` will copy `a`, and when `t = 1`, `q` will copy `b`.
* `[a] -> [q] tanhlimit`: This applies the hyperbolic tangent (tanh) function to track `a` to produce track `q`, for the purpose of preventing clipping while preserving dynamic range.

#### Stereo Mix
* `[a] -> [q] invert`: This switches the left and right tracks in `a`.
* `[a] -> [q] pan [pan]`: This pans `a` by a factor of `pan`. A value of 0 is centered, -1 is fully panned left, and 1 is fully panned right.

#### Equalization
* `[a] -> [q] lowpass [hz]`: This simple low-pass filter sets `q` to be `a` with a low-pass centered on the frequency of `hz` hertz.
* `[a] -> [q] basichighpass`: This is a very basic high-pass filter. I'm not experienced enough in digital audio processing algorithms to know how to add a frequency setting to this.

#### Delay
* `[a] -> [q] delay [ms] [t]`: This applies a delay effect to track `a`, with a delay of `ms` milliseconds and a feedback factor of `t`. So if `t` is set to `0.3`, for instance, then each echo will be `0.3` times as loud as the previous one.
* `[a] -> [q] delayinvert [ms] [t]`: This is the same delay effect, but this one also switches the stereo channels in the signal with every delay. This is helpful for reverb filters, for instance.

#### Pitch Shift
* `[a] -> [q] pitchshift [pitch] [cutoff]`: This applies a basic pitch-shifting effect to `a` to produce `q`. Here, `pitch` is a multiplier; i.e. the pitch frequency of `q` will be the pitch frequency of `a` times `pitch`. So if you want to pitch-shift by `n` cents, you should find the value of 2^(`n`/1200) and use that as your `pitch` value. (Keep in mind that this effect is probably too rough to be usable for precise musical filters.) The value `cutoff` is a frequency in hertz controlling the length of the window used by the block; frequencies below the value will not be pitch-shifted, but the lower the value is, the more latency will be introduced.
* `[a] -> [q] pitchshift [pitch]`: This is the same as above, but it uses the default `cutoff` value of 172.
* `[a] -> [q] rectify`: This takes the absolute value of the signal `[a]`. This is used to create an octave-up effect by some guitar pedals.

#### Modulation
* `[a] [b] -> [q] mult`: This multiplies the signals `a` and `b` together. This can be used for some modulation effects.
* `[a] [b] [c] -> [q] modmix`: This is effectively the `mix` block, but with the mix factor determined by a third track. When `c` is `-1`, `q` will be `a`, and when `c` is `1`, `q` will be `b`.
* `[a] [b] -> [q] modpan`: This pans `a`, where the pan factor is given by `[b]`. You can use this for LFO-based panning, for instance.

#### Signal Generation
* `[q] sine [hz]`: This generates a constant sine wave of `hz` hertz.
* `[q] saw [hz]`: This generates a constant sawtooth wave of `hz` hertz.
* `[q] square [hz]`: This generates a constant square wave of `hz` hertz.
* `[q] square [hz] [duty]`: This generates a constant pulse wave of `hz` hertz, with the duty cycle set to `duty`. So a value of 0.25 for `duty` will create a 25% pulse.
* `[q] triangle [hz]`: This generates a constant triangle wave of `hz` hertz.
* `[q] keypress [key]`: This generates a signal that is `1` or `-1` depending on whether or not the key named by `key` is pressed.
* `[q] wavfile [fname]`: Provide in `fname` the path to a signed 16-bit stereo WAV file from where the program is run. Then, `q` will be a track that loops the WAV file constantly. This does not resample intelligently (it uses nearest-neighbor), so for best results, use a file with the same sample rate as the one in config.json.
