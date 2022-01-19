#!/usr/bin/env python3

import os
import asyncio
import websockets
import pathlib
import ssl
import json
import datetime
from voice_authentication import stream2wavfile_int16
from voice_service import voice_database, remove_voice, enroll_voice, auth_voice
from s3_utils import upload_to_bucket

USERS = {}
MAX_CONNECTION = 5
MAX_ERROR_MESSAGE = 'The number of connected clients has reached the maximum. Please try again later.'


async def notify_response(websocket, result):
    """
    result: string (json dumped)
    """
    client_ip = websocket.remote_address[0]
    if USERS and client_ip in USERS:  # asyncio.wait doesn't accept an empty list
        await asyncio.wait([USERS[user]['ws'].send(result) for user in USERS if client_ip == user])


async def register(websocket):
    client_ip = websocket.remote_address[0]
    if client_ip in USERS:
        print('Reconnection: {}'.format(client_ip))
        del USERS[client_ip]

    if len(USERS) >= MAX_CONNECTION:
        print(client_ip, MAX_ERROR_MESSAGE)
        await notify_response(websocket,
                              json.dumps({
                                  'task': 'alert',
                                  'message': MAX_ERROR_MESSAGE
                              }))
    else:
        USERS[client_ip] = {
            'ws': websocket,
            'rec_count': 0,
            'spk_name': '',
            'rec_data': [],
        }
        print('New connection from {}'.format(client_ip))


def refresh_buffer(websocket):
    client_ip = websocket.remote_address[0]
    if client_ip in USERS:
        USERS[client_ip]['rec_count'] = 0
        USERS[client_ip]['rec_data'] = []


def set_speaker_name(websocket, speaker_name):
    client_ip = websocket.remote_address[0]
    if client_ip in USERS and speaker_name != '':
        USERS[client_ip]['spk_name'] = speaker_name
    else:
        USERS[client_ip] = {
            'ws': websocket,
            'rec_count': 0,
            'spk_name': speaker_name,
            'rec_data': [],
        }


async def unregister(websocket):
    try:
        client_ip = websocket.remote_address[0]
        if client_ip in USERS:
            del USERS[client_ip]
            print('Closed connection {}'.format(client_ip))
    except Exception as error:
        print('Unregister error: {}'.format(repr(error)))


async def ws_server(websocket, path):
    # register(websocket) sends user_event() to websocket
    await register(websocket)

    try:
        async for message in websocket:
            client_ip = websocket.remote_address[0]
            if client_ip not in USERS:
                await notify_response(websocket,
                                      json.dumps({
                                          'task': 'alert',
                                          'message': MAX_ERROR_MESSAGE
                                      }))
            else:

                try:
                    if isinstance(message, str):
                        try:
                            ws_command = json.loads(message)
                            """
                            'message' should be JSON like following:
                                {
                                    task: ‘enrollment / verification / identification’,
                                    spk_name: 'Sreehari',
                                    data: "audio buffer"
                                }
                            """
                            now = datetime.datetime.utcnow()
                            task = ws_command['task']

                            if task == 'get_voice_list':
                                voice_list = voice_database()
                                await notify_response(websocket, voice_list)
                                print('Get voice list:\n{}'.format(voice_list))
                                continue
                            elif task == 'remove_voice':
                                spk_name = ws_command['spk_name']
                                result = remove_voice(spk_name)
                                await notify_response(websocket, result)
                                print('Remove voice:\n{}'.format(result))
                                continue

                            if task not in ['enroll', 'verify', 'identify']:
                                print('task invalid.')
                                continue
                            record_status = ws_command['record']
                            if record_status == 'start':
                                audio_buf = list(ws_command['data'].values())
                                USERS[client_ip]['rec_data'].extend(audio_buf)
                                USERS[client_ip]['rec_count'] += 1
                                if USERS[client_ip]['rec_count'] < 15 * 7:  # length is less than 7 seconds
                                    continue

                            spk_name = ws_command['spk_name']
                            # set_speaker_name(websocket, spk_name)

                            if task == 'enroll':
                                tmp_audio_file = "./uploads/{}.wav".format(spk_name)
                                remote_file = "{}_{}_{}.wav".format(task, spk_name,
                                                                    now.strftime('%Y-%m-%d_%H-%M-%S'))
                            else:
                                tmp_audio_file = "./uploads/{}.wav".format(now.strftime('%Y-%m-%d_%H-%M-%S'))
                                remote_file = "{}_{}.wav".format(task, now.strftime('%Y-%m-%d_%H-%M-%S'))

                            audio_buf = USERS[client_ip]['rec_data']
                            refresh_buffer(websocket)

                            if not stream2wavfile_int16(audio_buf, tmp_audio_file):
                                result_json = {
                                    'status': 'false',
                                    'task': task,
                                    'message': 'Error in audio processing.'
                                }
                                await notify_response(websocket, json.dumps(result_json, indent=2))
                                continue

                            # upload to s3 folder
                            upload_to_bucket(tmp_audio_file, remote_file)

                            # TODO:
                            if task == 'enroll':
                                res = enroll_voice(tmp_audio_file, spk_name)
                                await notify_response(websocket, res)
                            else:
                                res = auth_voice(tmp_audio_file, task, spk_name)
                                await notify_response(websocket, res)

                        except Exception as error:
                            await notify_response(websocket,
                                                  json.dumps({
                                                      'status': 'false',
                                                      'task': 'alert',
                                                      'message': repr(error)
                                                  }))

                    else:
                        pass

                except Exception as error:
                    await notify_response(websocket,
                                          json.dumps({
                                              'status': 'false',
                                              'task': 'alert',
                                              'message': repr(error)
                                          }))

    except websockets.ConnectionClosed as e:
        print(e)
    except Exception as error:
        print("WebSocket message error: {}".format(repr(error)))
    finally:
        await unregister(websocket)


if __name__ == '__main__':
    ssl_option = True
    if ssl_option:
        # start Websockets server
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        certfile = pathlib.Path(__file__).with_name("fullchain1.pem")
        keyfile = pathlib.Path(__file__).with_name("privkey1.pem")
        ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile, password=None)

        start_server = websockets.serve(ws_server, "0.0.0.0", 5555, ssl=ssl_context)
    else:
        start_server = websockets.serve(ws_server, "0.0.0.0", 5555)

    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
