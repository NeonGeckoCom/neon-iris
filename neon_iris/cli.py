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

import logging
from pprint import pformat

import click

from os import environ
from os.path import expanduser, isfile
from time import sleep
from click_default_group import DefaultGroup
from ovos_utils.log import LOG

from neon_iris.util import load_config_file
from neon_iris.version import __version__

environ.setdefault("OVOS_CONFIG_BASE_FOLDER", "neon")
environ.setdefault("OVOS_CONFIG_FILENAME", "diana.yaml")
# TODO: Define default config file from this package


def _print_config():
    from ovos_config.config import Configuration
    config = Configuration().get('MQ')
    mq_endpoint = f"{config.get('server')}:{config.get('port', 5672)}"
    click.echo(f"Connecting to {mq_endpoint}")


@click.group("iris", cls=DefaultGroup,
             no_args_is_help=True, invoke_without_command=True,
             help="Iris: Interactive Relay for Intelligence Systems.\n\n"
                  "See also: iris COMMAND --help")
@click.option("--version", "-v", is_flag=True, required=False,
              help="Print the current version")
def neon_iris_cli(version: bool = False):
    if version:
        click.echo(f"Iris version {__version__}")


@neon_iris_cli.command(help="Create an MQ client session")
@click.option('--mq_config', '-m',
              help="Path to MQ Config file")
@click.option('--user-config', '-u',
              help="Path to User Config file")
@click.option('--lang', '-l', default="en-us",
              help="Language to accept input in")
@click.option('--audio', '-a', is_flag=True, default=False,
              help="Flag to enable audio playback")
def start_client(mq_config, user_config, lang, audio):
    from neon_iris.client import CLIClient
    _print_config()
    if mq_config:
        mq_config = load_config_file(expanduser(mq_config))
    else:
        from ovos_config.config import Configuration
        mq_config = Configuration().get("MQ")
    if user_config:
        user_config = load_config_file(expanduser(user_config))
    client = CLIClient(mq_config, user_config)
    LOG.init({"level": logging.WARNING})  # TODO: Debug flag?

    client.audio_enabled = audio
    click.echo("Enter '!{lang}' to change language\n"
               "Enter '!quit' to quit.\n"
               "Enter '!mute' or '!unmute' to change audio playback")
    try:
        while True:
            query = click.prompt("Query")
            if query.startswith('!'):
                if query == "!quit":
                    break
                elif query == "!mute":
                    click.echo("Disabling Audio Playback")
                    client.audio_enabled = False
                elif query == "!unmute":
                    click.echo("Enabling Audio Playback")
                    client.audio_enabled = True
                else:
                    query = query.lstrip('!')
                    query = expanduser(query)
                    if isfile(query):
                        client.send_audio(query, lang, client.username,
                                          client.user_profiles)
                    else:
                        lang = query.split()[0]
                        client.user_profiles[0]["speech"]["secondary_tts_language"] = lang
                        click.echo(f"Language set to {lang}")
            else:
                client.send_utterance(query, lang)
                # Pad prompt for multiple responses
                sleep(1)
    except Exception as e:
        click.echo(e)
    click.echo("Shutting Down Client")
    client.shutdown()


@neon_iris_cli.command(help="Create an MQ listener session")
def start_listener():
    from neon_iris.voice_client import NeonVoiceClient
    from ovos_utils import wait_for_exit_signal
    client = NeonVoiceClient()
    _print_config()
    wait_for_exit_signal()
    client.shutdown()


@neon_iris_cli.command(help="Create a GradIO Client session")
def start_gradio():
    from neon_iris.web_client import GradIOClient
    _print_config()
    try:
        chat = GradIOClient()
        chat.run()
    except OSError:
        click.echo("Unable to connect to MQ server")


@neon_iris_cli.command(help="Query Neon Core for supported languages")
def get_languages():
    from neon_iris.util import query_neon
    _print_config()
    resp = query_neon("neon.languages.get", {})
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Transcribe an audio file")
@click.option('--lang', '-l', default='en-us',
              help="language of input audio")
@click.argument("audio_file")
def get_stt(audio_file, lang):
    from neon_iris.util import get_stt
    _print_config()
    resp = get_stt(audio_file, lang)
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Transcribe an audio file")
@click.option('--lang', '-l', default='en-us',
              help="language of input audio")
@click.argument("utterance")
def get_tts(utterance, lang):
    from neon_iris.util import get_tts
    _print_config()
    resp = get_tts(utterance, lang)
    click.echo(pformat(resp))


# Backend
@neon_iris_cli.command(help="Query a weather endpoint")
@click.option('--unit', '-u', default='imperial',
              help="units to use ('metric' or 'imperial')")
@click.option('--latitude', '--lat', default=47.6815,
              help="location latitude")
@click.option('--longitude', '--lon', default=-122.2087,
              help="location latitude")
@click.option('--api', '-a', default='onecall',
              help="api to query ('onecall' or 'weather')")
def get_weather(unit, latitude, longitude, api):
    from neon_iris.util import query_api
    _print_config()
    query = {"lat": latitude,
             "lon": longitude,
             "units": unit,
             "api": api,
             "service": "open_weather_map"}
    resp = query_api(query)
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Query a stock price endpoint")
@click.argument('symbol')
def get_stock_quote(symbol):
    from neon_iris.util import query_api
    _print_config()
    query = {"symbol": symbol,
             "api": "quote",
             "service": "alpha_vantage"}
    resp = query_api(query)
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Query a stock symbol endpoint")
@click.argument('company')
def get_stock_symbol(company):
    from neon_iris.util import query_api
    _print_config()
    query = {"company": company,
             "api": "symbol",
             "service": "alpha_vantage"}
    resp = query_api(query)
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Query a WolframAlpha endpoint")
@click.option('--api', '-a', default='short',
              help="Wolfram|Alpha API to query")
@click.option('--unit', '-u', default='imperial',
              help="units to use ('metric' or 'imperial')")
@click.option('--latitude', '--lat', default=47.6815,
              help="location latitude")
@click.option('--longitude', '--lon', default=-122.2087,
              help="location latitude")
@click.argument('question')
def get_wolfram_response(api, unit, latitude, longitude, question):
    from neon_iris.util import query_api
    _print_config()
    query = {"api": api,
             "units": unit,
             "latlong": f"{latitude},{longitude}",
             "query": question,
             "service": "wolfram_alpha"}
    resp = query_api(query)
    click.echo(pformat(resp))


@neon_iris_cli.command(help="Converse with an LLM")
@click.option('--llm', default="chat_gpt",
              help="LLM Queue to interact with ('chat_gpt' or 'fastchat')")
def start_llm_chat(llm):
    from neon_iris.llm import LLMConversation
    _print_config()
    conversation = LLMConversation(llm)
    while True:
        query = click.prompt(">")
        resp = conversation.get_response(query)
        click.echo(resp)


@neon_iris_cli.command(help="Converse with an LLM")
def get_coupons():
    from neon_iris.util import get_brands_coupons
    data = get_brands_coupons()
    click.echo(pformat(data))


@neon_iris_cli.command(help="Parse a Neon CCL script")
@click.argument("script_file")
def parse_script(script_file):
    from neon_iris.util import parse_ccl_script
    data = parse_ccl_script(script_file)
    click.echo(pformat(data))

# TODO: email, metrics
