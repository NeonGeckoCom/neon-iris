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
from typing import List, Dict, Tuple
from uuid import uuid4

import gradio

from threading import Event
from ovos_bus_client import Message
from ovos_config import Configuration
from ovos_utils import LOG
from ovos_utils.json_helper import merge_dict

from neon_utils.file_utils import decode_base64_string_to_file
from ovos_utils.xdg_utils import xdg_data_home

from neon_iris.client import NeonAIClient


class GradIOClient(NeonAIClient):
    def __init__(self, lang: str = None):
        config = Configuration()
        self.config = config.get('iris') or dict()
        NeonAIClient.__init__(self, config.get("MQ"))
        self._await_response = Event()
        self._response = None
        self._transcribed = None
        self._current_tts = dict()
        self._profiles: Dict[str, dict] = dict()
        self._audio_path = join(xdg_data_home(), "iris", "stt")
        if not isdir(self._audio_path):
            makedirs(self._audio_path)
        self.default_lang = lang or self.config.get('default_lang')
        self.chat_ui = gradio.Blocks()
        LOG.name = "iris"
        LOG.init(self.config.get("logs"))

    def get_lang(self, session_id: str):
        if session_id and session_id in self._profiles:
            return self._profiles[session_id]['speech']['stt_language']
        return self.user_config['speech']['stt_language'] or self.default_lang

    @property
    def supported_languages(self) -> List[str]:
        """
        Get a list of supported languages from configuration
        @returns: list of BCP-47 language codes
        """
        return self.config.get('languages') or [self.default_lang]

    def _start_session(self):
        sid = uuid4().hex
        self._current_tts[sid] = None
        self._profiles[sid] = self.user_config
        self._profiles[sid]['user']['username'] = sid
        return sid

    def update_profile(self, stt_lang: str, tts_lang: str, tts_lang_2: str,
                       time: int, date: str, uom: str, city: str, state: str,
                       country: str, first: str, middle: str, last: str,
                       pref_name: str, email: str, session_id: str):
        """
        Callback to handle user settings changes from the web UI
        """
        location_dict = dict()
        if any((city, state, country)):
            from neon_utils.location_utils import get_coordinates, get_timezone
            try:
                location_dict = {"city": city, "state": state,
                                 "country": country}
                lat, lon = get_coordinates(location_dict)
                location_dict["lat"] = lat
                location_dict["lng"] = lon
                location_dict["tz"], location_dict["utc"] = get_timezone(lat,
                                                                         lon)
                LOG.debug(f"Got location update: {location_dict}")
            except Exception as e:
                LOG.exception(e)

        profile_update = {"speech": {"stt_language": stt_lang,
                                     "tts_language": tts_lang,
                                     "secondary_tts_language": tts_lang_2},
                          "units": {"time": time, "date": date, "measure": uom},
                          "location": location_dict,
                          "user": {"first_name": first, "middle_name": middle,
                                   "last_name": last,
                                   "preferred_name": pref_name, "email": email}}
        old_profile = self._profiles.get(session_id) or self.user_config
        self._profiles[session_id] = merge_dict(old_profile, profile_update)
        LOG.info(f"Updated profile for: {session_id}")
        return session_id

    def on_user_input(self, utterance: str,
                      chat_history: List[Tuple[str, str]],
                      audio_input: str,
                      client_session: str) -> (List[Tuple[str, str]], str, str, None, str):
        """
        Callback to handle textual user input
        @param utterance: String utterance submitted by the user
        @returns: Input box contents, Updated chat history, Gradio session ID, audio input, audio output
        """
        input_time = time()
        LOG.debug(f"Input received")
        if not self._await_response.wait(30):
            LOG.error("Previous response not completed after 30 seconds")
        in_queue = time() - input_time
        self._await_response.clear()
        self._response = None
        self._transcribed = None
        gradio_id = client_session
        lang = self.get_lang(gradio_id)
        if utterance:
            LOG.info(f"Sending utterance: {utterance} with lang: {lang}")
            self.send_utterance(utterance, lang, username=gradio_id,
                                user_profiles=[self._profiles[gradio_id]],
                                context={"gradio": {"session": gradio_id},
                                         "timing": {"wait_in_queue": in_queue,
                                                    "gradio_sent": time()}})
        else:
            LOG.info(f"Sending audio: {audio_input} with lang: {lang}")
            self.send_audio(audio_input, lang, username=gradio_id,
                            user_profiles=[self._profiles[gradio_id]],
                            context={"gradio": {"session": gradio_id},
                                     "timing": {"wait_in_queue": in_queue,
                                                "gradio_sent": time()}})
            chat_history.append(((audio_input, None), None))
        if not self._await_response.wait(30):
            LOG.error("No response received after 30s")
            self._await_response.set()
        self._response = self._response or "ERROR"
        LOG.info(f"Got response={self._response}")
        if utterance:
            chat_history.append((utterance, self._response))
        elif isinstance(self._transcribed, str):
            LOG.info(f"Got transcript: {self._transcribed}")
            chat_history.append((self._transcribed,  self._response))
        chat_history.append((None, (self._current_tts[gradio_id], None)))
        return chat_history, gradio_id, "", None, self._current_tts[gradio_id]

    # def play_tts(self, session_id: str):
    #     LOG.info(f"Playing most recent TTS file {self._current_tts}")
    #     return self._current_tts.get(session_id), session_id

    def run(self):
        """
        Blocking method to start the web server
        """
        self._await_response.set()
        title = self.config.get("webui_title", "Neon AI")
        description = self.config.get("webui_description", "Chat With Neon")
        chatbot_label = self.config.get("webui_chatbot_label") or description
        speech = self.config.get("webui_mic_label") or description
        text_label = self.config.get("webui_text_label") or description
        placeholder = self.config.get("webui_input_placeholder",
                                      "Ask me something")
        address = self.config.get("server_address") or "0.0.0.0"
        port = self.config.get("server_port") or 7860

        with self.chat_ui as blocks:
            client_session = gradio.State(self._start_session())
            client_session.attach_load_event(self._start_session, None)
            # Define primary UI
            blocks.title = title
            chatbot = gradio.Chatbot(label=chatbot_label)
            with gradio.Row():
                textbox = gradio.Textbox(label=text_label,
                                         placeholder=placeholder,
                                         scale=8)
                audio_input = gradio.Audio(source="microphone",
                                           type="filepath",
                                           label=speech,
                                           scale=2)
                submit = gradio.Button(value="Submit",
                                       variant="primary")
            tts_audio = gradio.Audio(autoplay=True, visible=False)
            submit.click(self.on_user_input,
                         inputs=[textbox, chatbot, audio_input,
                                 client_session],
                         outputs=[chatbot, client_session, textbox,
                                  audio_input, tts_audio])
            textbox.submit(self.on_user_input,
                           inputs=[textbox, chatbot, audio_input,
                                   client_session],
                           outputs=[chatbot, client_session, textbox,
                                    audio_input, tts_audio])
            # with gradio.Row():
            #     tts_button = gradio.Button("Play TTS")
            #     tts_button.click(self.play_tts,
            #                      inputs=[client_session],
            #                      outputs=[tts_audio, client_session])
            # Define settings UI
            with gradio.Row():
                with gradio.Column():
                    lang = self.get_lang(client_session.value).split('-')[0]
                    stt_lang = gradio.Radio(label="Input Language",
                                            choices=self._languages.get("stt")
                                            or self.supported_languages,
                                            value=lang)
                    tts_lang = gradio.Radio(label="Response Language",
                                            choices=self._languages.get("tts")
                                            or self.supported_languages,
                                            value=lang)
                    tts_lang_2 = gradio.Radio(label="Second Response Language",
                                              choices=[None] +
                                              (self._languages.get("tts") or
                                               self.supported_languages),
                                              value=None)
                with gradio.Column():
                    time_format = gradio.Radio(label="Time Format",
                                               choices=[12, 24],
                                               value=12)
                    date_format = gradio.Radio(label="Date Format",
                                               choices=["MDY", "YMD", "DMY",
                                                        "YDM"],
                                               value="MDY")
                    unit_of_measure = gradio.Radio(label="Units of Measure",
                                                   choices=["imperial",
                                                            "metric"],
                                                   value="imperial")
                with gradio.Column():
                    city = gradio.Textbox(label="City")
                    state = gradio.Textbox(label="State")
                    country = gradio.Textbox(label="Country")
                with gradio.Column():
                    first_name = gradio.Textbox(label="First Name")
                    middle_name = gradio.Textbox(label="Middle Name")
                    last_name = gradio.Textbox(label="Last Name")
                    pref_name = gradio.Textbox(label="Preferred Name")
                    email_addr = gradio.Textbox(label="Email Address")
                    # TODO: DoB, pic, about, phone?
            submit = gradio.Button("Update User Settings")
            submit.click(self.update_profile,
                         inputs=[stt_lang, tts_lang, tts_lang_2, time_format,
                                 date_format, unit_of_measure, city, state,
                                 country, first_name, middle_name, last_name,
                                 pref_name, email_addr, client_session],
                         outputs=[client_session])
            blocks.launch(server_name=address, server_port=port)

    def handle_klat_response(self, message: Message):
        """
        Handle a valid response from Neon. This includes text and base64-encoded
        audio in all requested languages.
        @param message: Neon response message
        """
        LOG.debug(f"gradio context={message.context['gradio']}")
        resp_data = message.data["responses"]
        files = []
        sentences = []
        session = message.context['gradio']['session']
        for lang, response in resp_data.items():
            sentences.append(response.get("sentence"))
            if response.get("audio"):
                for gender, data in response["audio"].items():
                    filepath = "/".join([self.audio_cache_dir] +
                                        response[gender].split('/')[-4:])
                    # TODO: This only plays the most recent, so it doesn't
                    #  support multiple languages or multi-utterance responses
                    self._current_tts[session] = filepath
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
        if message.msg_type == "neon.audio_input.response":
            self._transcribed = message.data.get("transcripts", [""])[0]

    def _handle_profile_update(self, message: Message):
        updated_profile = message.data["profile"]
        session_id = updated_profile['user']['username']
        if session_id in self._profiles:
            LOG.info(f"Got profile update for {session_id}")
            self._profiles[session_id] = updated_profile
        else:
            LOG.warning(f"Ignoring profile update for {session_id}")

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
