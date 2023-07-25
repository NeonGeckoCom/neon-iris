# Neon Iris
Neon Iris (Interactive Relay for Intelligence Systems) provides tools for
interacting with Neon systems remotely, via [MQ](https://github.com/NeonGeckoCom/chat_api_mq_proxy).

Install the Iris Python package with: `pip install neon-iris`
The `iris` entrypoint is available to interact with a bus via CLI. Help is available via `iris --help`.


## Debugging a Diana installation
The `iris` CLI includes utilities for interacting with a `Diana` backend.

### Configuration
Configuration files can be specified via environment variables. By default, 
`Iris` will set default values:
```
OVOS_CONFIG_BASE_FOLDER=neon
OVOS_CONFIG_FILENAME=diana.yaml
```

The example below would override defaults to read configuration from
`~/.config/mycroft/mycroft.conf`.
```
export OVOS_CONFIG_BASE_FOLDER=mycroft
export OVOS_CONFIG_FILENAME=mycroft.conf
```

More information about configuration handling can be found 
[in the docs](https://neongeckocom.github.io/neon-docs/quick_reference/configuration/).