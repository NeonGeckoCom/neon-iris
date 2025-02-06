# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
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

import pika.exceptions

from time import sleep
from asyncio import Event as AsyncEvent
from threading import Event, Thread
from neon_mq_connector.utils.client_utils import MQConnector
from ovos_utils import LOG
from pika.adapters.select_connection import SelectConnection
from pika.channel import Channel


class IrisConnector(MQConnector, Thread):
    async_consumers_enabled = True

    def __init__(self, *args, **kwargs):
        vhost = kwargs.pop('vhost')
        # TODO: service_name chosen for backwards-compat. and should be updated
        #   to something more descriptive
        kwargs['service_name'] = 'mq_handler'
        Thread.__init__(self, daemon=True)
        MQConnector.__init__(self, *args, **kwargs)
        self.vhost = vhost
        self._ready = AsyncEvent()
        self._channel_closed = Event()
        self._stopping = False

        self._connection = self.init_connection()

    def wait_for_connection(self):
        async def _wait_for_connection():
            sleep(0.5)

        LOG.info("Waiting for connection")
        while not self._ready.is_set():
            self.connection.ioloop.add_callback_threadsafe(_wait_for_connection)
        LOG.info("Connected!")

    @property
    def connection(self) -> SelectConnection:
        if self._connection is None:
            self._connection = self.init_connection()
        return self._connection

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def run(self, *args, **kwargs):
        MQConnector.run(self)
        self._connection.ioloop.start()

    def init_connection(self) -> SelectConnection:
        return SelectConnection(
            parameters=self.get_connection_params(self.vhost),
            on_open_callback=self.on_connected,
            on_open_error_callback=self.on_connection_fail,
            on_close_callback=self.on_close)

    def on_connected(self, _: pika.SelectConnection):
        """Called when we are fully connected to RabbitMQ"""
        LOG.info("MQ Connected")
        self.connection.channel(on_open_callback=self.on_channel_open)

    def on_connection_fail(self, *_, **__):
        """ Called when connection to RabbitMQ fails"""
        LOG.error(f"Failed to connect to MQ")
        self._connection = None

    def on_channel_open(self, new_channel: Channel):
        """Called when our channel has opened"""
        LOG.info(f"MQ Channel opened.")
        new_channel.add_on_close_callback(self.on_channel_close)
        self._ready.set()

    def on_channel_close(self, *_, **__):
        LOG.info(f"Channel closed.")
        self._channel_closed.set()

    def on_close(self, _: pika.SelectConnection, e: Exception):
        if isinstance(e, pika.exceptions.ConnectionClosed):
            LOG.info(f"Connection closed normally: {e}")
        elif isinstance(e, pika.exceptions.StreamLostError):
            LOG.warning("MQ connection lost; "
                        "RabbitMQ is likely temporarily unavailable.")
        else:
            LOG.error(f"MQ connection closed due to exception: {e}")
        if not self._stopping:
            # Connection was gracefully closed by the server. Try to re-connect
            LOG.info(f"Trying to reconnect after server closed connection")
            self._connection = self.init_connection()

    def shutdown(self):
        """
        Clean up this object. Closes all connections and stops any processing.
        """
        try:
            self._stopping = True
            if self.connection and not (self.connection.is_closed or
                                        self.connection.is_closing):
                self.connection.close()
                LOG.info(f"Waiting for channel close")
                if not self._channel_closed.wait(15):
                    raise TimeoutError(f"Timeout waiting for channel close.")

                # Wait for the connection to close
                waiter = Event()
                while not self.connection.is_closed:
                    waiter.wait(1)
                LOG.info(f"Connection closed")

            if self.connection:
                self.connection.ioloop.stop()
            MQConnector.stop(self)
            self._ready.clear()

        except Exception as e:
            LOG.error(f"Failed to close connection: {e}")
