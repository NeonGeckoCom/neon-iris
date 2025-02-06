# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
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


import unittest
from threading import Thread

import pytest

from os import environ
from neon_minerva.integration.rabbit_mq import rmq_instance
from neon_mq_connector import MQConnector
from pika.adapters.select_connection import SelectConnection

environ['TEST_RMQ_USERNAME'] = "test_user"
environ['TEST_RMQ_PASSWORD'] = "test_password"
environ['TEST_RMQ_VHOSTS'] = "/neon_chat_api"


@pytest.mark.usefixtures("rmq_instance")
class TestClient(unittest.TestCase):
    mq_config = {"server": "localhost",
                 "port": None,
                 "users": {"mq_handler": {"user": "test_user",
                                          "password": "test_password"}}}

    def setUp(self):
        if self.mq_config["port"] is None:
            self.mq_config["port"] = self.rmq_instance.port

    def test_lifecycle(self):
        from neon_iris.mq_connector import IrisConnector
        connector = IrisConnector(vhost="/neon_chat_api", config=self.mq_config)
        self.assertIsInstance(connector, MQConnector)
        self.assertIsInstance(connector.connection, SelectConnection)
        self.assertFalse(connector.ready)

        # Start the connector
        thread = Thread(target=connector.run)
        thread.start()
        connector.wait_for_connection()
        self.assertTrue(connector.ready)

        # Stop the connector
        connector.shutdown()
        self.assertFalse(connector.ready)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
