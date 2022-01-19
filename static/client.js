// peer connection
var pc = null;
var dc = null, dcInterval = null;

start_btn = document.getElementById('rec-start');
stop_btn = document.getElementById('rec-stop');

var bConnected = false;
//var ASRServerUrl = 'https://v2.id.s.zoispeech.com:5555/';
var ASRServerUrl = 'http://192.168.31.78:5000/';

let bufferSize = 4096,
	AudioContext,
	context,
	processor,
	input,
	globalStream;

var socket;
//vars
let streamStreaming = false;

function btn_show_stop() {
    start_btn.disabled = true;
    stop_btn.disabled = false;
}

function btn_show_start() {
    start_btn.disabled = false;
    stop_btn.disabled = true;
}

btn_show_start();

function negotiate() {
    return pc.createOffer().then(function (offer) {
        return pc.setLocalDescription(offer);
    }).then(function () {
        return new Promise(function (resolve) {
            if (pc.iceGatheringState === 'complete') {
                resolve();
            } else {
                function checkState() {
                    if (pc.iceGatheringState === 'complete') {
                        pc.removeEventListener('icegatheringstatechange', checkState);
                        resolve();
                    }
                }

                pc.addEventListener('icegatheringstatechange', checkState);
            }
        });
    }).then(function () {
        var offer = pc.localDescription;
        console.log(offer.sdp);
        return fetch(ASRServerUrl + '/offer', {
            body: JSON.stringify({
                sdp: offer.sdp,
                type: offer.type,
            }),
            headers: {
                'Content-Type': 'application/json'
            },
            method: 'POST'
        });
    }).then(function (response) {
        return response.json();
    }).then(function (answer) {
        console.log(answer.sdp);
        return pc.setRemoteDescription(answer);
    }).catch(function (e) {
        console.log(e);
        btn_show_start();
    });
}

//socket = new WebSocket("wss://v2.id.s.zoispeech.com:5555/ws");
socket = new WebSocket("ws://192.168.31.78:5000/ws");
socket.onclose = function(evt)
{
    bConnected = false;
    stop();
    alert('WebSocket closed. Try again by refreshing your browser.');
};

socket.onopen = function(evt) {
    bConnected = true;
    update_speaker_list();
};

socket.onmessage = function(evt) {
    var data = evt.data;
    var msg = JSON.parse(data);

    if (msg.task == "get_voice_list") {
        // remove all from list
        var sel = document.getElementById("voice_list");
        var length = sel.options.length;
        for (i = length-1; i >= 0; i--) {
          sel.options[i] = null;
        }

        spk_list = msg['message'];
        var select = document.getElementById("voice_list");
        for (const val of spk_list)
        {
            var option = document.createElement("option");
            option.value = val;
            option.text = val;
            select.appendChild(option);
        }
    } else if (msg.task == "alert") {
        alert(msg.message);
    } else if (msg.task == "remove_voice") {
        $("#msg_txt").val(msg.message);
    } else if (msg.task == "enroll") {
        $("#msg_txt").val(msg.message);
    } else if (msg.task == "verify" || msg.task == "identify") {
        $("#msg_txt").val($("#msg_txt").val() + '\r\n' + msg.message);
        //$("#msg_txt").value += msg.message + '\r\n';
    }
};

function start() {
    if (navigator.mediaDevices) {
        console.log('getUserMedia supported.');

        if (bConnected) {
            btn_show_stop();

            var constraints = {
                audio: true,
                video: false,
            };

            streamStreaming = true;
            AudioContext = window.AudioContext || window.webkitAudioContext;
            context = new AudioContext({
                // if Non-interactive, use 'playback' or 'balanced' // https://developer.mozilla.org/en-US/docs/Web/API/AudioContextLatencyCategory
                latencyHint: 'playback',
            });

            // Create a ScriptProcessorNode with a bufferSize of 4096 and a single input and output channel
            processor = context.createScriptProcessor(bufferSize, 1, 1);
            processor.connect(context.destination);
            context.resume();

            var microphoneProcess = function (e) {
                var left = e.inputBuffer.getChannelData(0);
                // var left16 = convertFloat32ToInt16(left); // old 32 to 16 function
                var left16 = downsampleBuffer(left, 44100, 16000)
                var task = document.getElementById('enrollment').value;
                var spkname = document.getElementById('spkname').value;
                if (spkname == "" && (task == "verify" || task == "enroll")) {
                    console.log("Please input speaker name to be enrolled or verified.");
                } else {
                    var ws_command = {
                        'task': task,
                        'record': 'start',
                        'spk_name': spkname,
                        'data': left16
                    };
                    socket.send(JSON.stringify(ws_command), json=true);
                }
            }


            navigator.mediaDevices.getUserMedia(constraints).then(function (stream) {
                globalStream = stream;
                input = context.createMediaStreamSource(stream);
                input.connect(processor);

                processor.onaudioprocess = function (e) {
                    microphoneProcess(e);
                };
            }, function (err) {
                console.log('Could not acquire media: ' + err);
                btn_show_start();
            });
        } else {
            alert('WebSocket closed. Try again by refreshing your browser.');
        }
    } else {
        alert('This has getUserMedia not supported.');
    }
}

function stop() {

    streamStreaming = false;
    if (globalStream) {
        let track = globalStream.getTracks()[0];
        track.stop();
    }

    if (input) {
    	input.disconnect(processor);
    }
    if (processor) {
    	processor.disconnect(context.destination);
    }
    if (context) {
        context.close().then(function () {
            input = null;
            processor = null;
            context = null;
            AudioContext = null;
        });
    }

    btn_show_start();

    var task = document.getElementById('enrollment').value;
    var speaker_name = document.getElementById('spkname').value;
    var ws_command = {
        'task': task,
        'record': 'stop',
        'spk_name': speaker_name,
        'data': []
    };
    socket.send(JSON.stringify(ws_command), json=true);

    if (task == "enroll")
        update_speaker_list();
}

function update_speaker_list()
{
    if (bConnected) {
        var ws_command = {
            'task': 'get_voice_list',
            'spk_name': '',
            'data': []
        };
        socket.send(JSON.stringify(ws_command), json=true);
    } else {
        alert('WebSocket closed. Try again by refreshing your browser.');
    }
};

function remove_voice()
{
    if (bConnected) {
        var speaker_name = document.getElementById('voice_list').value;
        if (speaker_name == "") {
            alert("Please choose speaker name to be deleted.");
        } else {
            var ws_command = {
                'task': 'remove_voice',
                'spk_name': speaker_name,
                'data': []
            };
            socket.send(JSON.stringify(ws_command), json=true);
        }
    } else {
        alert('WebSocket closed. Try again by refreshing your browser.');
    }

    update_speaker_list();
};

var downsampleBuffer = function (buffer, sampleRate, outSampleRate) {
	if (outSampleRate == sampleRate) {
		return buffer;
	}
	if (outSampleRate > sampleRate) {
		throw "downsampling rate show be smaller than original sample rate";
	}
	var sampleRateRatio = sampleRate / outSampleRate;
	var newLength = Math.round(buffer.length / sampleRateRatio);
	var result = new Int16Array(newLength);
	var offsetResult = 0;
	var offsetBuffer = 0;
	while (offsetResult < result.length) {
		var nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
		var accum = 0, count = 0;
		for (var i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
			accum += buffer[i];
			count++;
		}

		result[offsetResult] = Math.min(1, accum / count) * 0x7FFF;
		offsetResult++;
		offsetBuffer = nextOffsetBuffer;
	}
	return result;
}

function download()
{
	$.get(ASRServerUrl + "/wav_path", function(data) {
		console.log(data);
		$("#download_href").attr("href", ASRServerUrl + "/"+data).attr("download",ASRServerUrl + "/"+data);
		$("#download_href")[0].click();
	})
}

