from os.path import join, dirname

from neon_iris.client import CLIClient

default_config = {
    "server": "mq.2022.us",
    "port": 25672,
    "users": {
        "mq_handler": {
            "user": "neon_api_utils",
            "password": "Klatchat2021"
        }
    }
}

client = CLIClient(default_config)
client.handle_tts_request("Hello", "en-us")
client.handle_stt_request(join(dirname(__file__), "what time is it .wav"),
                          "en-us")
client.shutdown()
