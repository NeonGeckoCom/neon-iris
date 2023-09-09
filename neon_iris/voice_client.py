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

import wave

from threading import Event, Thread
from time import time
from unittest.mock import Mock
from os.path import join, isdir, dirname
from os import makedirs

from ovos_plugin_manager.microphone import OVOSMicrophoneFactory
from ovos_plugin_manager.vad import OVOSVADFactory
from ovos_dinkum_listener.voice_loop.voice_loop import DinkumVoiceLoop
from ovos_dinkum_listener.voice_loop.hotwords import HotwordContainer
from ovos_config.config import Configuration
from ovos_utils.messagebus import FakeBus
from ovos_utils.log import LOG
from ovos_utils.xdg_utils import xdg_data_home
from ovos_utils.sound import play_wav
from ovos_bus_client.message import Message
from neon_utils.file_utils import decode_base64_string_to_file
from neon_iris.client import NeonAIClient


class MockTransformers(Mock):
    def transform(self, chunk):
        return chunk, dict()


class NeonVoiceClient(NeonAIClient):
    def __init__(self, bus=None):
        self.config = Configuration()
        NeonAIClient.__init__(self, self.config.get("MQ"))
        self.bus = bus or FakeBus()
        self._mic = OVOSMicrophoneFactory.create(self.config)
        self._mic.start()
        self._hotwords = HotwordContainer(self.bus)
        self._hotwords.load_hotword_engines()
        self._vad = OVOSVADFactory.create(self.config)

        self._voice_loop = DinkumVoiceLoop(mic=self._mic,
                                           hotwords=self._hotwords,
                                           stt=Mock(),
                                           fallback_stt=Mock(),
                                           vad=self._vad,
                                           transformers=MockTransformers(),
                                           stt_audio_callback=self.on_stt_audio,
                                           listenword_audio_callback=self.on_hotword_audio)
        self._voice_loop.start()
        self._voice_thread = None

        self._stt_audio_path = join(xdg_data_home(), "iris", "stt")
        self._tts_audio_path = join(xdg_data_home(), "iris", "tts")
        if not isdir(self._stt_audio_path):
            makedirs(self._stt_audio_path)
        if not isdir(self._tts_audio_path):
            makedirs(self._tts_audio_path)

        self._listening_sound = join(dirname(__file__), "res",
                                     "start_listening.wav")

        self.run()

    def run(self):
        self._voice_thread = Thread(target=self._voice_loop.run, daemon=True)
        self._voice_thread.start()

    def on_stt_audio(self, audio_bytes: bytes, context: dict):
        LOG.info(f"Got {len(audio_bytes)} bytes of audio")
        wav_path = join(self._stt_audio_path, f"{time()}.wav")
        with open(wav_path, "wb") as wav_io, \
                wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(self._mic.sample_rate)
            wav_file.setsampwidth(self._mic.sample_width)
            wav_file.setnchannels(self._mic.sample_channels)
            wav_file.writeframes(audio_bytes)

        self.send_audio(wav_path)
        LOG.debug("Sent Audio to MQ")

    def on_hotword_audio(self, audio: bytes, context: dict):
        payload = context
        msg_type = "recognizer_loop:wakeword"
        play_wav(self._listening_sound)
        LOG.info(f"Emitting hotword event: {msg_type}")
        # emit ww event
        self.bus.emit(Message(msg_type, payload, context))

    def handle_klat_response(self, message: Message):
        responses = message.data.get('responses')
        for lang, data in responses.items():
            text = data.get('sentence')
            LOG.info(text)
            file_basename = f"{hash(text)}.wav"
            genders = data.get('genders', [])
            for gender in genders:
                audio_data = data["audio"].get(gender)
                audio_file = join(self._tts_audio_path, lang, gender,
                                  file_basename)
                try:
                    decode_base64_string_to_file(audio_data, audio_file)
                except FileExistsError:
                    pass
                play_wav(audio_file)

    def handle_complete_intent_failure(self, message: Message):
        LOG.info(f"{message.data}")

    def handle_api_response(self, message: Message):
        LOG.info(f"{message.data}")

    def handle_error_response(self, message: Message):
        LOG.error(f"Got error response: {message.data}")

    def clear_caches(self, message: Message):
        pass

    def clear_media(self, message: Message):
        pass

    def shutdown(self):
        self._voice_loop.stop()
        self._voice_thread.join(30)
        NeonAIClient.shutdown(self)
