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
from abc import abstractmethod

from os import makedirs
from os.path import join, isfile
from pprint import pformat
from queue import Queue
from tempfile import gettempdir
from threading import Event, Thread
from time import time
from typing import Optional
from uuid import uuid4

from mycroft_bus_client import Message
from pika.exceptions import StreamLostError

from neon_utils.configuration_utils import get_neon_user_config, get_neon_local_config
from neon_utils.mq_utils import NeonMQHandler
from neon_utils.socket_utils import b64_to_dict
from neon_utils.file_utils import decode_base64_string_to_file, encode_file_to_base64_string
from neon_utils.logger import LOG


class NeonAIClient:
    def __init__(self, mq_config: dict = None, user_config: dict = None):
        self._uid = str(uuid4())
        self._vhost = "/neon_chat_api"
        self._client = "mq_api"
        self.client_name = "tester"
        self._config = mq_config or get_neon_local_config().content.get("MQ")
        self._connection = self._init_mq_connection()

        self.audio_cache_dir = join(gettempdir(), "neon_iris")
        makedirs(self.audio_cache_dir, exist_ok=True)

    @property
    def uid(self):
        return self._uid

    @property
    def connection(self):
        if not self._connection.connection.is_open:
            LOG.warning("Connection closed")
            self._connection.stop()
            self._connection = self._init_mq_connection()
        try:
            self._connection.connection.channel()
        except StreamLostError:
            LOG.warning("Connection unexpectedly closed, recreating")
            self._connection.stop()
            self._connection = self._init_mq_connection()

        return self._connection

    def shutdown(self):
        self._connection.stop()

    @abstractmethod
    def handle_neon_response(self, channel, method, _, body):
        """
        Override this method to handle Neon Responses
        """

    @abstractmethod
    def handle_neon_error(self, channel, method, _, body):
        """
        Override this method to handle Neon Error Responses
        """

    def send_utterance(self, utterance: str, lang: str = "en-us",
                       username: Optional[str] = None,
                       user_profiles: Optional[list] = None):
        """
        Optionally override this to queue text inputs or do any pre-parsing
        :param utterance: utterance to submit to skills module
        :param lang: language code associated with request
        :param username: username associated with request
        :param user_profiles: user profiles expecting a response
        """
        self._send_utterance(utterance, lang, username, user_profiles)

    def send_audio(self, audio_file: str, lang: str = "en-us",
                   username: Optional[str] = None,
                   user_profiles: Optional[list] = None):
        """
        Optionally override this to queue audio inputs or do any pre-parsing
        :param audio_file: path to audio file to send to speech module
        :param lang: language code associated with request
        :param username: username associated with request
        :param user_profiles: user profiles expecting a response
        """
        self._send_audio(audio_file, lang, username, user_profiles)

    def _build_message(self, msg_type: str, data: dict,
                       username: Optional[str] = None,
                       user_profiles: Optional[list] = None,
                       ident: str = None) -> Message:
        return Message(msg_type, data,
                       {"client_name": self.client_name,
                        "client": self._client,
                        "ident": ident or str(time()),
                        "username": username,
                        "user_profiles": user_profiles or list(),
                        "klat": {"routing_key": self.uid}
                        })

    def _send_utterance(self, utterance: str, lang: str,
                        username: str, user_profiles: list):
        message = self._build_message("recognizer_loop:utterance",
                                      {"utterances": [utterance],
                                       "lang": lang}, username, user_profiles)
        serialized = {"msg_type": message.msg_type,
                      "data": message.data,
                      "context": message.context}
        self._send_serialized_message(serialized)

    def _send_audio(self, audio_file: str, lang: str,
                    username: str, user_profiles: list):
        audio_data = encode_file_to_base64_string(audio_file)
        message = self._build_message("neon.audio_input",
                                      {"lang": lang,
                                       "audio_data": audio_data},
                                      username, user_profiles)
        serialized = {"msg_type": message.msg_type,
                      "data": message.data,
                      "context": message.context}
        self._send_serialized_message(serialized)

    def _send_serialized_message(self, serialized: dict):
        try:
            self.connection.emit_mq_message(
                self._connection.connection,
                queue="neon_chat_api_request",
                request_data=serialized)
        except Exception as e:
            LOG.exception(e)
            self.shutdown()

    def _init_mq_connection(self):
        mq_connection = NeonMQHandler(self._config, "mq_handler", self._vhost)
        mq_connection.register_consumer("neon_response_handler", self._vhost,
                                        self.uid, self.handle_neon_response,
                                        auto_ack=False)
        mq_connection.register_consumer("neon_error_handler", self._vhost,
                                        "neon_chat_api_error", self.handle_neon_error,
                                        auto_ack=False)
        mq_connection.run(daemon=True)
        return mq_connection


class CLIClient(NeonAIClient):
    def __init__(self, mq_config: dict = None, user_config: dict = None):
        super().__init__(mq_config=mq_config)
        user_config = user_config or \
            json.loads(json.dumps(get_neon_user_config().content))
        self.user_profiles = [user_config]
        self.username = user_config["user"]["username"]
        self.audio_enabled = True
        self._response_event = Event()
        self._request_queue = Queue()

        Thread(target=self._handle_next_request, daemon=True).start()

    @staticmethod
    def _play_audio(audio_file: str):
        """
        Handle local audio playback
        :param audio_file: audio file to play back
        """
        playback_cmd = "mpg123" if audio_file.endswith(".mp3") else "paplay"
        subprocess.Popen([playback_cmd, audio_file],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).wait()

    def _handle_next_request(self):
        """
        Threaded process to continue handling queued requests
        """
        while True:
            request = self._request_queue.get()
            if not request:
                break
            utterance, lang = request
            self._response_event.clear()
            self._send_utterance(utterance, lang, self.username,
                                 self.user_profiles)
            self._response_event.wait(30)

    def handle_neon_response(self, channel, method, _, body):
        """
        Handle an MQ Neon response
        """
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

    def handle_neon_error(self, channel, method, _, body):
        """
        Handle and MQ Neon error
        """
        response = b64_to_dict(body)
        if response.get("context").get("routing_key") == self.uid:
            channel.basic_ack(delivery_tag=method.delivery_tag)
            LOG.error(response)
        else:
            channel.basic_nack(delivery_tag=method.delivery_tag)
            LOG.debug("Error for other client ignored")

    def send_utterance(self, utterance: str, lang: str = "en-us",
                       _=None, __=None):
        """
        Queue a string request for skills processing
        :param utterance: User utterance to submit
        :param lang: language of utterance
        """
        self._response_event.clear()
        self._request_queue.put((utterance, lang))
        if not self._response_event.wait(30):
            print(f"No repsonse to: {utterance}")
        while not self._request_queue.empty():
            self._response_event.wait(30)

    def send_audio(self, audio_file: str, lang: str = "en-us",
                   _=None,
                   __=None):
        """
        Send an audio file for skills processing
        :param audio_file: Audio File to submit for STT processing
        :param lang: language of audio
        """
        self._response_event.clear()
        self._send_audio(audio_file, lang, self.username, self.user_profiles)
        if not self._response_event.wait(30):
            print(f"No repsonse to: {audio_file}")

    def shutdown(self):
        """
        Shutdown the client
        """
        self._request_queue.put(None)
        super().shutdown()
