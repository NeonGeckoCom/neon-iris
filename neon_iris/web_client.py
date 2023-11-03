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
from os.path import isfile

import gradio

from threading import Event
from ovos_bus_client import Message
from ovos_config import Configuration
from ovos_utils import LOG

from neon_utils.file_utils import decode_base64_string_to_file

from neon_iris.client import NeonAIClient


class GradIOClient(NeonAIClient):
    def __init__(self, lang: str = None):
        self.config = Configuration()
        NeonAIClient.__init__(self, self.config.get("MQ"))
        self._await_response = Event()
        self._response = None
        self.lang = lang or self.config.get('lang', 'en-us')
        self.chat_ui = gradio.Blocks()

    def on_user_input(self, utterance: str, *args, **kwargs):
        LOG.info(args)
        LOG.info(kwargs)
        self._await_response.clear()
        self._response = None
        self.send_utterance(utterance, self.lang)
        self._await_response.wait(30)
        LOG.info(f"Response={self._response}")
        return self._response

    def run(self):
        title = "Neon AI"
        description = "Chat With Neon"
        placeholder = "Ask me something"
        audio_input = gradio.Audio(source="microphone", type="filepath")
        chatbot = gradio.Chatbot(label=description)
        textbox = gradio.Textbox(placeholder=placeholder)
        with self.chat_ui as blocks:
            gradio.ChatInterface(self.on_user_input,
                                 chatbot=chatbot,
                                 textbox=textbox,
                                 additional_inputs=audio_input,
                                 title=title,
                                 retry_btn=None,
                                 undo_btn=None)
            blocks.launch(server_name="0.0.0.0", server_port=7860)

    def handle_klat_response(self, message: Message):
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
                    files.append(filepath)
                    if not isfile(filepath):
                        decode_base64_string_to_file(data, filepath)
        self._response = "\n".join(sentences)
        self._await_response.set()

    def handle_complete_intent_failure(self, message: Message):
        self._response = "ERROR"
        self._await_response.set()

    def handle_api_response(self, message: Message):
        pass

    def handle_error_response(self, message: Message):
        pass

    def clear_caches(self, message: Message):
        pass

    def clear_media(self, message: Message):
        pass
