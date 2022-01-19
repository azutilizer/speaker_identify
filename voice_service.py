import os
import json
import contextlib
import wave
import shutil
from webrtcvad import Vad
from voice_authentication import extract_feature, load_embeddings, \
    audio_authentication, embedding_folder

UPLOAD_FOLDER = os.path.join('.', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def trim_audio_ffmpeg(src_file, start_tm, end_tm, dst_file):
    if not os.path.exists(src_file):
        return False
    if os.path.isfile(dst_file):
        os.remove(dst_file)

    try:
        cmd = 'ffmpeg -i {} -ar 16000 -ac 1 -acodec pcm_s16le -ss {:.2f} -to {:.2f} {} ' \
              '-y -loglevel panic'.format(src_file, start_tm, end_tm, dst_file)
        os.system(cmd)
        return True
    except Exception as error:
        print('Error: {}'.format(repr(error)))
        return False


def read_wave(path):
    """Reads a .wav file.
    Takes the path, and returns (PCM audio data, sample rate).
    """
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000, 48000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate


class Frame(object):
    """Represents a "frame" of audio data."""
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
    """Generates audio frames from PCM audio data.
    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.
    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n


def vad_audio_segment(audio_file, gap_size=0.5, frame_duration=10):
    """
    :param audio_file:
    :param gap_size: gap between neighbour segments (seconds)
    :param frame_duration: frame step (milli seconds)
    :return:
    """
    vad = Vad(3)

    audio, sample_rate = read_wave(audio_file)
    frames = frame_generator(frame_duration, audio, sample_rate)
    frames = list(frames)

    vad_segment = []
    for i, frame in enumerate(frames):
        is_speech = vad.is_speech(frame.bytes, sample_rate)
        if is_speech:
            vad_segment.append([frame.timestamp, frame.timestamp+frame.duration])

    if len(vad_segment) == 0:
        return []
    audio_segment = [vad_segment[0]]
    for x in vad_segment[1:]:
        if x[0] <= audio_segment[-1][1] + gap_size:
            audio_segment[-1][1] = x[1]
        else:
            audio_segment.append(x)

    return audio_segment


def voice_database():
    response_data = {
        'status': 'false',
        'task': 'get_voice_list'
    }
    try:
        embedding_list = [x for x in os.listdir(embedding_folder) if x.endswith(".pth")]
        speaker_name_list = [x[:-4] for x in embedding_list]
        response_data["status"] = "true"
        response_data["message"] = speaker_name_list
        response = json.dumps(response_data, indent=2)
    except Exception as error:
        response_data["message"] = repr(error)
        response = json.dumps(response_data, indent=2)
    return response


def enroll_voice(audio_file, spk_name):
    response_data = {
        "status": "fail",
        "task": "enroll",
        "message": "Invalid payload."
    }

    print("Enroll request ...")
    pth_path = extract_feature(audio_file)
    if os.path.isfile(pth_path):
        response_data["status"] = 'success'
        response_data["message"] = 'Voice has successfully registered with name: {}.'.format(
            spk_name
        )
    response = json.dumps(response_data, indent=2)
    return response


def auth_voice(audio_file, task, spk_name):
    print("Authentication request ...")
    result_json = {
        'status': 'false',
        'task': task,
        'message': 'Invalid payload.'
    }

    # check if there's pre-registered embeddings.
    embedding_list = [x for x in os.listdir(embedding_folder) if x.endswith(".pth")]
    if len(embedding_list) == 0:
        result_json["message"] = "Not registered any voice. Please enroll, first."
        response = json.dumps(result_json, indent=2)
        return response

    # convert uploaded audio to standard format
    convert_audio_file = os.path.join(UPLOAD_FOLDER, os.path.basename(audio_file)[:-4]+"_convert.wav")
    convert_cmd = "ffmpeg -i \"{}\" -acodec pcm_s16le -ac 1 -ar 16000 \"{}\" -y -loglevel panic".format(
        audio_file,
        convert_audio_file
    )
    try:
        os.system(convert_cmd)
    except Exception as error:
        result_json["message"] = repr(error)
        response = json.dumps(result_json, indent=2)
        return response
    """
    # segmentation
    segments = vad_audio_segment(convert_audio_file)
    if len(segments) == 0:
        result_json["message"] = "Empty audio data."
        response = json.dumps(result_json, indent=2)
        os.remove(convert_audio_file)
        return response

    os.makedirs('tmp', exist_ok=True)
    id_result = []
    for i, seg in enumerate(segments):
        stime, etime = seg
        tmp_file = os.path.join('tmp', '{}.wav'.format(i+1))
        if not trim_audio_ffmpeg(convert_audio_file, stime, etime, tmp_file):
            continue

        embeddings = load_embeddings()
        score, spk, result, spk_score = audio_authentication(convert_audio_file, embeddings)

        if task == "verify":
            score = spk_score[spk_name].item(0)
            if score >= 0.84:
                trans_text = "Verified as {} with score {:.3f}".format(spk_name, score)
            else:
                trans_text = "Rejected as score {:.3f}".format(score)
        else:  # "identify"
            if result == 'Accepted':
                trans_text = "Identified as {} with score {:.3f}".format(best_spk, score.item(0))
            else:
                trans_text = "Rejected as score {:.3f}".format(score.item(0))

    shutil.rmtree('tmp', ignore_errors=True)
    """

    spk_pth = '{}.pth'.format(spk_name)

    embeddings = load_embeddings()
    score, best_spk, result, spk_score = audio_authentication(convert_audio_file, embeddings)

    if task == "verify":
        if spk_pth not in embedding_list:
            result_json['spk_name'] = spk_name
            result_json['confidence'] = 0
            result_json['message'] = 'not registered.'
        else:
            score = spk_score[spk_name].item(0)
            result_json['spk_name'] = spk_name
            result_json['confidence'] = score
            if score >= 0.84:
                result_json['status'] = 'true'
                result_json['message'] = '{} verified as score {}.'.format(spk_name, score)
            else:
                result_json['message'] = '{} not verified as score {}.'.format(spk_name, score)
    else:  # "identify"
        result_json['spk_name'] = best_spk
        result_json['confidence'] = score.item(0)
        result_json['message'] = '{}: could not find any matches.(score: {:.3f})'.format(spk_name, score.item(0))
        if result == 'Accepted':
            result_json['status'] = 'true'
            result_json['message'] = '{}: Found a match with score {:.3f}.'.format(spk_name, score.item(0))

    response = json.dumps(result_json, indent=2)
    os.remove(convert_audio_file)

    return response


def remove_voice(spk_name):
    response_data = {
        "status": "false",
        "task": "remove_voice",
        "message": "Error while remove the voice."
    }

    try:
        embedding_path = os.path.join(embedding_folder, "{}.pth".format(spk_name))
        os.remove(embedding_path)

        response_data["status"] = "true"
        response_data["message"] = "successfully removed."
    except Exception as error:
        response_data["message"] = repr(error)

    response = json.dumps(response_data, indent=2)
    return response
