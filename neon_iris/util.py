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

import json
import yaml

from os.path import isfile
from ovos_utils.log import LOG

from neon_utils.file_utils import encode_file_to_base64_string


def load_config_file(file_path: str) -> dict:
    """
    Load a config file (json or yaml) and return the dict contents
    :param file_path: path to config file to load
    """
    if not isfile(file_path):
        raise FileNotFoundError(f"Requested config file not found: {file_path}")
    with open(file_path) as f:
        try:
            config = json.load(f)
        except Exception as e:
            LOG.debug(e)
            f.seek(0)
            config = yaml.safe_load(f)
    return config


def query_api(query_params: dict, timeout: int = 10) -> dict:
    """
    Query an API service on the `/neon_api` vhost.
    :param query_params: dict query to send
    :param timeout: seconds to wait for a response
    :returns: dict MQ response
    """
    from neon_mq_connector.utils.client_utils import send_mq_request
    response = send_mq_request("/neon_api", query_params, "neon_api_input",
                               "neon_api_output", timeout)
    return response


def get_brands_coupons(timeout: int = 5) -> dict:
    """
    Get brands/coupons data on the `/neon_coupons` vhost.
    :param timeout: seconds to wait for a response
    :returns: dict MQ response
    """
    from neon_mq_connector.utils.client_utils import send_mq_request
    response = send_mq_request("/neon_coupons", {}, "neon_coupons_input",
                               "neon_coupons_output", timeout)
    return response


def parse_ccl_script(script_path: str, metadata: dict = None,
                     timeout: int = 30) -> dict:
    """
    Parse a nct script file into an ncs formatted file
    :param script_path: path to file to parse
    :param metadata: Optional dict metadata to include in output
    :param timeout: seconds to wait for a response
    :returns: dict MQ response
    """
    from neon_mq_connector.utils.client_utils import send_mq_request
    with open(script_path, 'r') as f:
        text = f.read()
    metadata = metadata or {}
    response = send_mq_request("/neon_script_parser", {"text": text,
                                                       "metadata": metadata},
                               "neon_script_parser_input",
                               "neon_script_parser_output", timeout)
    return response


def query_neon(msg_type: str, data: dict, timeout: int = 10) -> dict:
    """
    Query a Neon Core service on the `/neon_chat_api`
    :param msg_type: string message type to emit
    :param data: message data to send
    :param timeout: seconds to wait for a response
    """
    from neon_mq_connector.utils.client_utils import send_mq_request
    query = {"msg_type": msg_type, "data": data, "context": {"source": "iris"}}
    response = send_mq_request("/neon_chat_api", query, "neon_chat_api_request",
                               timeout=timeout)
    if response:
        response["context"]["session"] = \
            set(response["context"].pop("session").keys())
    return response


def get_stt(audio_file: str, lang: str = "en-us") -> dict:
    data = {"audio_file": audio_file,
            "audio_data": encode_file_to_base64_string(audio_file),
            "utterances": [""],  # TODO: For MQ Connector compat.
            "lang": lang}
    response = query_neon("neon.get_stt", data, 20)
    return response


def get_tts(string: str, lang: str = "en-us") -> dict:
    data = {"text": string,
            "utterance": string,  # TODO: For MQ Connector compat.
            "utterances": [""],  # TODO: For MQ Connector compat.
            "speaker": {"name": "Neon",
                        "language": lang,
                        "gender": "female"},  # TODO: For neon_audio compat.
            "lang": lang}
    response = query_neon("neon.get_tts", data)
    return response
