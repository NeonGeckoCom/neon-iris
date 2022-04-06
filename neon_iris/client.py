# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2021 Neongecko.com Inc.
# BSD-3
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json
import subprocess

from os import makedirs
from os.path import join, isfile
from pprint import pformat
from queue import Queue
from tempfile import gettempdir
from threading import Event, Thread
from time import time
from uuid import uuid4

from mycroft_bus_client import Message
from pika.exceptions import StreamLostError

from neon_utils.configuration_utils import get_neon_user_config, get_neon_local_config
from neon_utils.mq_utils import NeonMQHandler
from neon_utils.socket_utils import b64_to_dict
from neon_utils.file_utils import decode_base64_string_to_file


class NeonAIClient:
    def __init__(self, mq_config: dict = None, user_config: dict = None):
        self._uid = str(uuid4())
        self._vhost = "/neon_chat_api"
        self._client = "mq_api"
        self.client_name = "tester"
        self._config = mq_config or get_neon_local_config().content.get("MQ")
        self._connection = self._init_mq_connection()
        self._request_queue = Queue()
        self._response_event = Event()
        user_config = user_config or \
            json.loads(json.dumps(get_neon_user_config().content))
        self.user_profiles = [user_config]
        self.username = user_config["user"]["username"]
        self.audio_cache_dir = join(gettempdir(), "neon_iris")
        self.audio_enabled = True
        makedirs(self.audio_cache_dir, exist_ok=True)

        Thread(target=self._handle_next_request, daemon=True).start()

    @property
    def uid(self):
        return self._uid

    def shutdown(self):
        self._request_queue.put(None)
        self._connection.stop()

    def _play_audio(self, audio_file: str):
        playback_cmd = "mpg123" if audio_file.endswith(".mp3") else "paplay"
        subprocess.Popen([playback_cmd, audio_file],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).wait()

    def handle_neon_response(self, channel, method, _, body):
        channel.basic_ack(delivery_tag=method.delivery_tag)
        response = b64_to_dict(body)
        if response["msg_type"] == "klat.response":
            resp_data = response["data"]["responses"]
            files = []
            sentences = []
            for lang, response in resp_data.items():
                sentences.append(response.get("sentence"))
                if response.get("audio"):
                    for gender, data in response["audio"].items():
                        filepath = "/".join([self.audio_cache_dir] +
                                            response[gender].split('/')[-4:])
                        files.append(filepath)
                        if not isfile(filepath):
                            decode_base64_string_to_file(data, filepath)
            print(f"{pformat(sentences)}\n{pformat(files)}\n")
            if self.audio_enabled:
                for file in files:
                    self._play_audio(file)
        else:
            print(f"Response: {response['data']}\n")
        self._response_event.set()

    def _handle_next_request(self):
        while True:
            request = self._request_queue.get()
            if not request:
                break
            utterance, lang = request
            self._response_event.clear()
            self._send_request(utterance, lang)
            self._response_event.wait(30)

    def send_request(self, utterance: str, lang: str = "en-us"):
        self._response_event.clear()
        self._request_queue.put((utterance, lang))
        if not self._response_event.wait(30):
            print(f"No repsonse to: {utterance}")
        while not self._request_queue.empty():
            self._response_event.wait(30)

    def _send_request(self, utterance: str, lang: str):
        message = self._build_message(utterance, lang)
        serialized = {"msg_type": message.msg_type,
                      "data": message.data,
                      "context": message.context}
        try:
            self._connection.emit_mq_message(
                self._connection.connection,
                queue="neon_chat_api_request",
                request_data=serialized)
        except StreamLostError:
            print("Connection closed, attempting to re-establish")
            if self._connection.connection.is_open:
                self._connection.connection.close()
            self._connection = self._init_mq_connection()
            print("Reconnected, retrying request")
            self._request_queue.put((utterance, lang))
        except Exception as e:
            print(e)
            self.shutdown()

    def _build_message(self, utterance: str,
                       lang: str = "en-us",
                       ident: str = None):
        return Message("recognizer_loop:utterance",
                          {"utterances": [utterance],
                           "lang": lang},
                          {"client_name": self.client_name,
                           "client": self._client,
                           "ident": ident or str(time()),
                           "username": self.username,
                           "user_profiles": self.user_profiles,
                           "klat": {"routing_key": self.uid}
                           })

    def _init_mq_connection(self):
        mq_connection = NeonMQHandler(self._config, "mq_handler", self._vhost)
        mq_connection.register_consumer("neon_response_handler", self._vhost,
                                        self.uid, self.handle_neon_response,
                                        auto_ack=False)
        mq_connection.run_consumers(daemon=True)
        return mq_connection
