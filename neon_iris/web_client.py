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

from os import makedirs
from os.path import isfile, join, isdir
from time import time
from typing import List, Optional

import gradio

from threading import Event
from ovos_bus_client import Message
from ovos_config import Configuration
from ovos_utils import LOG
from neon_utils.file_utils import decode_base64_string_to_file
from ovos_utils.xdg_utils import xdg_data_home

from neon_iris.client import NeonAIClient
import librosa
import soundfile as sf


class GradIOClient(NeonAIClient):
    def __init__(self, lang: str = None):
        config = Configuration()
        self.config = config.get('iris') or dict()
        NeonAIClient.__init__(self, config.get("MQ"))
        self._await_response = Event()
        self._response = None
        self._current_tts = None
        self._audio_path = join(xdg_data_home(), "iris", "stt")
        if not isdir(self._audio_path):
            makedirs(self._audio_path)
        self.default_lang = lang or self.config.get('default_lang')
        self.chat_ui = gradio.Blocks()

    @property
    def lang(self):
        return self.user_config['speech']['stt_language'] or self.default_lang

    @property
    def supported_languages(self) -> List[str]:
        """
        Get a list of supported languages from configuration
        @returns: list of BCP-47 language codes
        """
        return self.config.get('languages') or [self.default_lang]

    def update_profile(self, stt_lang: str, tts_lang: str, tts_lang_2: str):
        """
        Callback to handle user settings changes from the web UI
        """
        # TODO: Per-client config. The current method of referencing
        #  `self._user_config` means every user shares one configuration which
        #  does not scale. This client should probably override the
        #  `self.user_config` property and implement a method for storing user
        #  configuration in cookies or similar.
        profile_update = {"speech": {"stt_language": stt_lang,
                                     "tts_language": tts_lang,
                                     "secondary_tts_language": tts_lang_2}}
        from neon_utils.user_utils import apply_local_user_profile_updates
        apply_local_user_profile_updates(profile_update, self._user_config)

    def send_audio(self, audio_file: str, lang: str = "en-us",
                   username: Optional[str] = None,
                   user_profiles: Optional[list] = None):
        """
        @param audio_file: path to wav audio file to send to speech module
        @param lang: language code associated with request
        @param username: username associated with request
        @param user_profiles: user profiles expecting a response
        """
        # TODO: Audio conversion is really slow here. check ovos-stt-http-server
        audio_file = self.convert_audio(audio_file)
        self._send_audio(audio_file, lang, username, user_profiles)

    def convert_audio(self, audio_file: str, target_sr=16000, target_channels=1,
                      dtype='int16') -> str:
        """
        @param audio_file: path to audio file to convert for speech model
        @returns: path to converted audio file
        """
        # Load the audio file
        y, sr = librosa.load(audio_file, sr=None, mono=False)  # Load without changing sample rate or channels

        # If the file has more than one channel, mix it down to one channel
        if y.ndim > 1 and target_channels == 1:
            y = librosa.to_mono(y)

        # Resample the audio to the target sample rate
        y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_sr)

        # Ensure the audio array is in the correct format (int16 for 2-byte samples)
        y_resampled = (y_resampled * (2 ** (8 * 2 - 1))).astype(dtype)

        output_path = join(self._audio_path, f"{time()}.wav")
        # Save the audio file with the new sample rate and sample width
        sf.write(output_path, y_resampled, target_sr, format='WAV', subtype='PCM_16')
        LOG.info(f"Converted audio file to {output_path}")
        return output_path

    def on_user_input(self, utterance: str, *args, **kwargs) -> str:
        """
        Callback to handle textual user input
        @param utterance: String utterance submitted by the user
        @returns: String response from Neon (or "ERROR")
        """
        # TODO: This should probably queue with a separate iterator thread
        LOG.debug(f"args={args}|kwargs={kwargs}")
        self._await_response.clear()
        self._response = None
        if utterance:
            LOG.info(f"Sending utterance: {utterance} with lang: {self.lang}")
            self.send_utterance(utterance, self.lang)
        else:
            LOG.info(f"Sending audio: {args[1]} with lang: {self.lang}")
            self.send_audio(args[1], self.lang)
        self._await_response.wait(30)
        self._response = self._response or "ERROR"
        LOG.info(f"Got response={self._response}")
        return self._response

    def play_tts(self):
        LOG.info(f"Playing most recent TTS file {self._current_tts}")
        return self._current_tts

    def run(self):
        """
        Blocking method to start the web server
        """
        title = self.config.get("webui_title", "Neon AI")
        description = self.config.get("webui_description", "Chat With Neon")
        chatbot = self.config.get("webui_chatbot_label") or description
        speech = self.config.get("webui_mic_label") or description
        placeholder = self.config.get("webui_input_placeholder",
                                      "Ask me something")
        address = self.config.get("server_address") or "0.0.0.0"
        port = self.config.get("server_port") or 7860

        chatbot = gradio.Chatbot(label=chatbot)
        textbox = gradio.Textbox(placeholder=placeholder)

        with self.chat_ui as blocks:
            # Define primary UI
            audio_input = gradio.Audio(source="microphone",
                                       type="filepath",
                                       label=speech)
            gradio.ChatInterface(self.on_user_input,
                                 chatbot=chatbot,
                                 textbox=textbox,
                                 additional_inputs=[audio_input],
                                 title=title,
                                 retry_btn=None,
                                 undo_btn=None, )
            tts_audio = gradio.Audio(autoplay=True, visible=True,
                                     label="Neon's Response")
            tts_button = gradio.Button("Play TTS")
            tts_button.click(self.play_tts,
                             outputs=[tts_audio])
            # Define settings UI
            with gradio.Row():
                with gradio.Column():
                    stt_lang = gradio.Radio(label="Input Language",
                                            choices=self.supported_languages,
                                            value=self.lang)
                    tts_lang = gradio.Radio(label="Response Language",
                                            choices=self.supported_languages,
                                            value=self.lang)
                    tts_lang_2 = gradio.Radio(label="Second Response Language",
                                              choices=[None] +
                                              self.supported_languages,
                                              value=None)
                    submit = gradio.Button("Update User Settings")
                with gradio.Column():
                    # TODO: Unit settings
                    pass
                with gradio.Column():
                    # TODO: Location settings
                    pass
                with gradio.Column():
                    # TODO Name settings
                    pass
            submit.click(self.update_profile,
                         inputs=[stt_lang, tts_lang, tts_lang_2])
            blocks.launch(server_name=address, server_port=port)

    def handle_klat_response(self, message: Message):
        """
        Handle a valid response from Neon. This includes text and base64-encoded
        audio in all requested languages.
        @param message: Neon response message
        """
        LOG.debug(f"Response_data={message.data}")
        resp_data = message.data["responses"]
        files = []
        sentences = []
        for lang, response in resp_data.items():
            sentences.append(response.get("sentence"))
            if response.get("audio"):
                for gender, data in response["audio"].items():
                    filepath = "/".join([self.audio_cache_dir] +
                                        response[gender].split('/')[-4:])
                    # TODO: This only plays the most recent, so it doesn't support
                    # multiple languages
                    self._current_tts = filepath
                    files.append(filepath)
                    if not isfile(filepath):
                        decode_base64_string_to_file(data, filepath)
        self._response = "\n".join(sentences)
        self._await_response.set()

    def handle_complete_intent_failure(self, message: Message):
        """
        Handle an intent failure response from Neon. This should not happen and
        indicates the Neon service is probably not yet ready.
        @param message: Neon intent failure response message
        """
        self._response = "ERROR"
        self._await_response.set()

    def handle_api_response(self, message: Message):
        """
        Catch-all handler for `.response` messages routed to this client that
        are not explicitly handled (i.e. get_stt, get_tts)
        @param message: Response message to something emitted by this client
        """
        LOG.debug(f"Got {message.msg_type}: {message.data}")

    def handle_error_response(self, message: Message):
        """
        Handle an error response from the MQ service attached to Neon. This
        usually indicates a malformed input.
        @param message: Response message indicating reason for failure
        """
        LOG.error(f"Error response: {message.data}")

    def clear_caches(self, message: Message):
        """
        Handle a request from Neon to clear cached data.
        @param message: Message requesting cache deletion. The context of this
            message will include the requesting user for user-specific caches
        """
        # TODO: remove cached TTS audio responses

    def clear_media(self, message: Message):
        """
        Handle a request from Neon to clear local multimedia. This method does
        not apply to this client as there is no user-generated media to clear.
        @param message: Message requesting media deletion
        """
        pass
