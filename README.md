# Neon Iris

Neon Iris (Interactive Relay for Intelligence Systems) provides tools for
interacting with Neon systems remotely, via [MQ](https://github.com/NeonGeckoCom/chat_api_mq_proxy).

Install the Iris Python package with: `pip install neon-iris`
The `iris` entrypoint is available to interact with a bus via CLI. Help is available via `iris --help`.

## Configuration

Configuration files can be specified via environment variables. By default,
`Iris` will read configuration from `~/.config/neon/diana.yaml` where
`XDG_CONFIG_HOME` is set to the default `~/.config`.
More information about configuration handling can be found
[in the docs](https://neongeckocom.github.io/neon-docs/quick_reference/configuration/).

> _Note:_ The neon-iris Docker image uses `neon.yaml` by default because the
> `iris` web UI is often deployed with neon-core.

A default configuration might look like:

```yaml
MQ:
  server: neonaialpha.com
  port: 25672
  users:
    mq_handler:
      user: neon_api_utils
      password: Klatchat2021
iris:
  default_lang: en-us
  languages:
    - en-us
    - uk-ua
  webui_chatbot_label: "Neon AI"
  webui_mic_label: "Speak with Neon"
  webui_input_placeholder: "Chat with Neon"
```

### Language Support

For Neon Core deployments that support language support queries via MQ, `languages`
may be removed and `enable_lang_api: True` added to configuration. This will use
the reported STT/TTS supported languages in place of any `iris` configuration.

## Interfacing with a Diana installation

The `iris` CLI includes utilities for interacting with a `Diana` backend. Use
`iris --help` to get a current list of available commands.

### `iris start-listener`

This will start a local wake word recognizer and use a remote Neon
instance connected to MQ for processing audio and providing responses.

### `iris start-gradio`

This will start a local webserver and serve a Gradio UI to interact with a Neon
instance connected to MQ.

### `iris start-client`

This starts a CLI client for typing inputs and receiving responses from a Neon
instance connected via MQ.

### `iris start-websat`

This starts a local webserver and serves a web UI for interacting with a Neon
instance connected to MQ.

## Docker

### Building

To build the Docker image, run:

```bash
docker build -t ghcr.io/neongeckocom/neon-iris:latest .
```

To build the Docker image with gradio extras, run:

```bash
docker build --build-arg EXTRAS=gradio -t ghcr.io/neongeckocom/neon-iris:latest .
```

To build the Docker image with websat extras, run:

```bash
docker build --build-arg EXTRAS=web_sat -t ghcr.io/neongeckocom/neon-iris:latest .
```

### Running

The Docker image that is built for this service runs the `iris` CLI with the
`-h` argument by default. In order to use the container to run different services,
you must override the entrypoint. For example, to run the `start-websat` service,
you would run:

```bash
docker run --rm -p 8000:8000 ghcr.io/neongeckocom/neon-iris:latest start-websat
```

Running the container without any arguments gives you a list of commands that
can be run. You can choose to run any of these commands by replacing `start-websat`
in the above command with the command you want to run.

## websat

### Configuration

The `websat` web UI is a simple web UI for interacting with a Neon instance. It
accepts special configuration items prefixed with `webui_` to customize the UI.

| parameter               | description                                                                                                                            | default                |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| webui_description       | The header text for the web UI                                                                                                         | Chat with Neon         |
| webui_title             | The title text for the web UI in the browser                                                                                           | Neon AI                |
| webui_input_placeholder | The placeholder text for the input box                                                                                                 | Ask me something       |
| webui_ws_url            | The websocket URL to connect to, which must be accessible from the browser you're running in. Note that the default will usually fail. | ws://localhost:8000/ws |

Iris uses the `Configuration()` class from OVOS to handle configuration. This
means that you can specify configuration in a `neon.yaml` file in the
`~/.config/neon`. When using a container, you can mount a volume to
`/home/neon/.config/neon` to provide a configuration file.

Example configuration block:

```yaml
iris:
  webui_title: Neon AI
  webui_description: Chat with Neon
  webui_input_placeholder: Ask me something
  webui_ws_url: wss://neonaialpha.com/ws
```

### Customization

The websat web UI reads in the following items from `neon_iris/static/custom`:

- `error.mp3` - Used for error responses
- `wake.mp3` - Used for wake word responses
- `favicon.ico` - The favicon for the web UI
- `logo.svg` - The logo for the web UI

To customize these items, you can replace them in the `neon_iris/static/custom` folder and rebuild the image.

### Websocket endpoint

The websat web UI uses a websocket to communicate with OpenWakeWord, which can
load `.tflite` or `.onnx` models. The websocket endpoint is `/ws`, but since it
is served with FastAPI, it also supports `wss` for secure connections. To
use `wss`, you must provide a certificate and key file.

### Chat history

The websat web UI stores chat history in the browser's [local storage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage).
This allows chat history to persist between browser sessions. However, it also
means that if you clear your browser's local storage, you will lose your chat
history. This is a feature, not a bug.
