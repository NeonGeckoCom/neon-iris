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
import logging
import click
import yaml

from os.path import expanduser, isfile
from time import sleep
from click_default_group import DefaultGroup

from neon_utils.logger import LOG
from neon_iris.client import CLIClient
from neon_iris.version import __version__


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
    if mq_config:
        with open(mq_config) as f:
            try:
                mq_config = json.load(f)
            except Exception as e:
                f.seek(0)
                mq_config = yaml.safe_load(f)
    if user_config:
        with open(user_config) as f:
            try:
                user_config = json.load(f)
            except Exception as e:
                user_config = None
    client = CLIClient(mq_config, user_config)
    LOG.init({"level": logging.WARNING})

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


if __name__ == "__main__":
    start_client(None, None, "en-us")
