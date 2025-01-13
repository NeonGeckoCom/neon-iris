# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
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

import os
import sys
import unittest

from neon_mq_connector.utils.client_utils import NeonMQHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_iris.client import NeonAIClient

_test_config = {
    "MQ": {
        "server": "mq.2022.us",
        "port": 25672,
        "users": {
            "mq_handler": {
                "user": "neon_api_utils",
                "password": "Klatchat2021"
            }
        }
    }
}


class TestClient(unittest.TestCase):
    def test_client_create(self):
        client = NeonAIClient(_test_config)
        self.assertIsInstance(client.uid, str)
        self.assertEqual(client._config, _test_config)
        self.assertEqual(client._connection.config, _test_config["MQ"])
        self.assertTrue(os.path.isdir(client.audio_cache_dir))
        self.assertIsInstance(client.client_name, str)
        self.assertIsInstance(client.connection, NeonMQHandler)
        self.assertEqual(client.connection.vhost, "/neon_chat_api")
        client.shutdown()


if __name__ == '__main__':
    unittest.main()
