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
> *Note:* The neon-iris Docker image uses `neon.yaml` by default because the
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
