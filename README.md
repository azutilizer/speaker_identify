# Speaker Identification Web Service

Simple voice recognition program based on VoiceFilter using d-vector emdeddings to extract audio characteristics.

Speaker enrollment and identification based con https://github.com/jymsuper/SpeakerRecognition_tutorial


## Install dependencies
```shell
sudo apt-get update
sudo apt-get install ffmpeg
sudo apt-get install python3-pip
pip3 install -r requirements.txt
```

## Change port number
```html
app.run(host='0.0.0.0', debug=True, port=7000)
```

## Run the service
```shell
python3 main.py
```

Running flags:

* --config: configuration file. Default ```config/default.yaml```
* --embedder path: path to the model that makes the embeddings. Default= ```embedder.pt```
* --spk_path (enroll.py only – required): path to the folder with the files of the speaker to register. The program will take each audio, produce an embedding that represents the person's voice characteristics, and finally average the embeddings to get a better representation. The name of the folder will be taken as the person's ID.
* --threshold: value between 0 and 1 to establish an acceptance threshold for identity verification
* --test_path (inference.py only - required): path to the audio file or folder for identification purposes.
* --embeddings_path: path to save/load the embeddings. Default: "embeddings/". If not passed or non existent will create a folder with that name.


## API endpoints

### Enrollment
```python
_api.add_resource(VoiceEnroll, '/voice_enroll')
```
parameters:
```python
{
    'task_flag': 'enroll',
    'spk_name': SPEAKER_NAME(string),
    'filename': AUDIO_FILE_NAME(string),
    'audio_data': AUDIO_BUFFER(base64)
}
```

### Get speaker list
```python
_api.add_resource(VoiceDataBase, '/get_voice_list')
```

### Remove speaker
```python
_api.add_resource(VoiceRemove, '/voice_remove')
```
parameters:
```python
{
    'spk_name': SPEAKER_NAME(string)
}
```

### Verification / Identification
```python
_api.add_resource(VoiceAuth, '/voice_auth')
```
parameters:
```python
{
    'task_flag': 'verify' (or 'identify'),
    'spk_name': SPEAKER_NAME(string) (not needed when identification),
    'filename': AUDIO_FILE_NAME(string),
    'audio_data': AUDIO_BUFFER(base64)
}
```


## Test

### LibriSpeech

Select a random number of files from the [LibriSpeech](http://www.openslr.org/12/) database and place for each speaker a file in the spk\_path folder and other in the test\_path folder. Each speaker has a number so that will serve as speaker ID. The predicted output must match that number.

### Noisy files

Generate noisy files from the Librispeech files using the following code:

* To add reverb to the audio

Install the following library:

```
pip install pysndfx
```

```
from pysndfx import AudioEffectsChain

fx = (AudioEffectsChain().reverb())
fx({name_of_input_file}, {name_of_output_file})
```

* To add white noise

Install the following library

```
pip install pydub
```

The amplitude level of the white noise is controlled by the `volume` parameter of the `WhiteNoise()` method

```
from pydub import AudioSegment
from pydub.generators import WhiteNoise
import os

for file in os.listdir('.'):
	sound = AudioSegment.from_file(file, 'wav')
	name = os.path.basename(file)
	name = name.strip('.wav')
	noise = WhiteNoise(sample_rate=16000).to_audio_segment(duration=len(sound), volume=-35.0)
	combined = sound.overlay(noise)
	combined.export(name+'noisy.wav', format="wav")
```

* Add noise with SpecAugment method (frequency distortion and time and frequency masking)

Refer to [this](https://github.com/DemisEom/SpecAugment.git) repository to use SpecAugment

## Results

The performance of the recognition system was tested with clean audios from the Librispeech dataset, with audios from whatsapp recorded on different phones and acoustic environments and corrupted Librispeech audios with reverb, white noise at different levels and SpecAugment.

The results are the following, before and after averaging, respectively:

* Librispeech: 100% | 100%
* Whatsapp audios: 100%
* Reverb: 100% | 100%
* SpecAugment: 43%
* White Noise (-20dB): 6% | 15%
* White Noise (-25dB): 14% | 55%
* White Noise (-30dB): 52% | 85% 
* White Noise (-35dB): 83% | 85%
* White Noise (-40dB): 100%
* White Noise (-50dB): 100%
