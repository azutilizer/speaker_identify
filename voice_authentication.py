import os
import sys
import datetime
import numpy as np
import torch
import torch.nn.functional as F
import librosa
from scipy.io.wavfile import write
from utils.audio import Audio
from utils.hparams import HParam
from model.embedder import SpeechEmbedder

cur_dir = os.path.dirname(os.path.realpath(__file__))
embedding_folder = os.path.join(cur_dir, 'embeddings')
os.makedirs(embedding_folder, exist_ok=True)
sys.path.append(cur_dir)


def print_log(log_text):
    now = datetime.datetime.utcnow()
    log_file = 'server_message.log'

    log_message = "{}: {}".format(now.strftime('%Y-%m-%d_%H-%M-%S'), log_text)
    print(log_message)
    with open(log_file, 'a', encoding='utf-8') as logfp:
        logfp.write("{}\n".format(log_message))


def get_embeddings(file_path, audio, embedder):
    """
    Produces de d-vector for each audio file
    """
    dvec_wav, _ = librosa.load(file_path, sr=16000)
    dvec_mel = audio.get_mel(dvec_wav)
    dvec_mel = torch.from_numpy(dvec_mel).float()
    dvec = embedder(dvec_mel)
    dvec = dvec.unsqueeze(0)
    return dvec


def load_embeddings(embeddings_path=embedding_folder):
    with torch.no_grad():
        embeddings = {}
        for file in os.listdir(embeddings_path):
            embeddings[file] = torch.load(os.path.join(embeddings_path, file))
        print("Embeddings loaded")
    return embeddings


def enroll(spk_path, audio, embedder, embeddings_path):
    """
    Takes the path to all the files to enroll.
    Return the dictionary (length: number of speakers)
    """

    if not os.path.exists(embeddings_path):
        os.makedirs(embeddings_path)
        print("Created directory: {}".format(embeddings_path))

    basename = os.path.basename(spk_path)
    spk_id = os.path.splitext(basename)[0]

    embedding = get_embeddings(spk_path, audio, embedder)

    path = os.path.join(embeddings_path, spk_id + '.pth')
    torch.save(embedding, path)

    print("Spk: {} aggregated".format(spk_id))

    return path, embedding


def extract_feature(spk_filepath):
    if not os.path.exists(spk_filepath):
        print("No such file: {}".format(spk_filepath))
        return ""

    conf_file = os.path.join(cur_dir, "config", "default.yaml")
    embeddings_path = os.path.join(cur_dir, "embeddings")
    os.makedirs(embeddings_path, exist_ok=True)

    embedder_path = os.path.join(cur_dir, "embedder.pt")
    hp = HParam(conf_file)

    with torch.no_grad():
        # Load model
        embedder = SpeechEmbedder(hp)
        if torch.cuda.is_available():
            chkpt_embed = torch.load(embedder_path)
        else:
            chkpt_embed = torch.load(embedder_path, map_location=torch.device('cpu'))
        embedder.load_state_dict(chkpt_embed)
        embedder.eval()
        print("Embedder loaded.")

        # Create an audio object
        audio = Audio(hp)

        # Get the embeddings (if embeddings_path exists it will load the file with the embeddings
        # and if it's not it will get the embeddings of spk_path)
        pth_path, pth_data = enroll(spk_filepath, audio, embedder, embeddings_path)

        return pth_path


def audio_authentication(test_audio_path, embeddings, threshold=0.84):
    conf_file = os.path.join(cur_dir, "config", "default.yaml")
    embedder_path = os.path.join(cur_dir, "embedder.pt")
    hp = HParam(conf_file)
    with torch.no_grad():
        # Load model
        embedder = SpeechEmbedder(hp)
        if torch.cuda.is_available():
            chkpt_embed = torch.load(embedder_path)
        else:
            chkpt_embed = torch.load(embedder_path, map_location=torch.device('cpu'))
        embedder.load_state_dict(chkpt_embed)
        embedder.eval()
    audio = Audio(hp)
    test_embedding = get_embeddings(test_audio_path, audio, embedder)
    max_score = -10 ** 8
    best_spk = None
    spk_score = {}

    for spk in embeddings:
        score = F.cosine_similarity(test_embedding, embeddings[spk])
        score = score.data.numpy()
        spk_score[os.path.splitext(spk)[0]] = score
        if score > max_score:
            max_score = score
            best_spk = spk

    if max_score < threshold:
        result = 'Rejected'
    else:
        result = 'Accepted'

    best_spk = os.path.splitext(best_spk)[0]
    score = max_score
    return score, best_spk, result, spk_score


def pcm2float(sig, dtype='float64'):
    sig = np.asarray(sig)
    if sig.dtype.kind not in 'iu':
        raise TypeError("'sig' must be an array of integers")
    dtype = np.dtype(dtype)
    if dtype.kind != 'f':
        raise TypeError("'dtype' must be a floating point type")

    i = np.iinfo(sig.dtype)
    abs_max = 2 ** (i.bits - 1)
    offset = i.min + abs_max
    return (sig.astype(dtype) - offset) / abs_max


def stream2wavfile(byte_stream, audio_file):
    try:
        # dvec_wav = pcm2float(np.frombuffer(byte_stream, dtype=np.int16), dtype='float32')
        librosa.output.write_wav(audio_file, np.ndarray(byte_stream), 16000)
        if os.path.isfile(audio_file):
            return True
    except Exception as error:
        print_log(repr(error))
    return False


def stream2wavfile_int16(int_array, audio_file):
    try:
        write(audio_file, 16000, np.asarray(int_array).astype(np.int16))
        return True
    except Exception as error:
        print_log(repr(error))
        return False


def stream_auth(byte_stream, threshold=0.84):
    dvec_wav = pcm2float(np.frombuffer(byte_stream, dtype=np.int16), dtype='float32')

    embedding_path = os.path.join(cur_dir, 'embeddings/')
    embeddings = load_embeddings(embedding_path)
    conf_file = os.path.join(cur_dir, "config", "default.yaml")
    embedder_path = os.path.join(cur_dir, "embedder.pt")
    hp = HParam(conf_file)
    with torch.no_grad():
        # Load model
        embedder = SpeechEmbedder(hp)
        if torch.cuda.is_available():
            chkpt_embed = torch.load(embedder_path)
        else:
            chkpt_embed = torch.load(embedder_path, map_location=torch.device('cpu'))
        embedder.load_state_dict(chkpt_embed)
        embedder.eval()
    audio = Audio(hp)

    dvec_mel = audio.get_mel(dvec_wav)
    dvec_mel = torch.from_numpy(dvec_mel).float()
    dvec = embedder(dvec_mel)
    test_embedding = dvec.unsqueeze(0)

    max_score = -10 ** 8
    best_spk = None
    spk_score = {}

    for spk in embeddings:
        score = F.cosine_similarity(test_embedding, embeddings[spk])
        score = score.data.numpy()
        spk_score[os.path.splitext(spk)[0]] = score
        if score > max_score:
            max_score = score
            best_spk = spk

    if max_score < threshold:
        result = 'Rejected'
    else:
        result = 'Accepted'

    best_spk = os.path.splitext(best_spk)[0]
    score = max_score
    return score, best_spk, result, spk_score
