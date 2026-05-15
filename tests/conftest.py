# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
# BSD-3 License

"""
Test session helpers.

Why this file exists
--------------------
The upstream ``neon_minerva.integration.rabbit_mq.rmq_instance`` fixture
starts a RabbitMQ subprocess but never tears it down. It relies on
``mirakuru``'s ``atexit`` cleanup hook to SIGKILL the process during
interpreter shutdown.

In GitHub Actions the Erlang VM that backs RabbitMQ does not always die
cleanly when the wrapper process is signalled at interpreter exit, which
leaves ``pytest`` blocked during shutdown. The tests themselves print as
``PASSED``, but the job hits the workflow timeout because the python process
never returns.

We:

* override the fixture with an explicit ``yield``/teardown so the broker is
  stopped as soon as the test class is done with it, and
* register a ``pytest_sessionfinish`` hook that arms a watchdog which forces
  the interpreter to exit if the normal shutdown hangs for too long.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest
from os import environ

from port_for import get_port
from pytest_rabbitmq.factories.executor import RabbitMqExecutor
from pytest_rabbitmq.factories.process import get_config


_ACTIVE_EXECUTORS: list[RabbitMqExecutor] = []
# Seconds we'll allow normal interpreter shutdown to take after the test
# session has finished before we force-exit. Generous enough that pytest can
# print its summary; short enough that the GHA job-level timeout won't fire.
_FORCE_EXIT_GRACE_SECONDS = 30


@pytest.fixture(scope="class")
def rmq_instance(request, tmp_path_factory):
    """Start a RabbitMQ subprocess for the test class and stop it after."""
    config = get_config(request)
    rabbit_ctl = config["ctl"]
    rabbit_server = config["server"]
    rabbit_host = "127.0.0.1"
    rabbit_port = get_port(config["port"])
    rabbit_distribution_port = get_port(
        config["distribution_port"], [rabbit_port]
    )
    assert rabbit_distribution_port
    assert rabbit_distribution_port != rabbit_port, (
        "rabbit_port and distribution_port can not be the same!"
    )

    tmpdir = tmp_path_factory.mktemp(f"pytest-rabbitmq-{request.fixturename}")
    rabbit_logpath = config["logsdir"] or (tmpdir / "logs")

    executor = RabbitMqExecutor(
        rabbit_server,
        rabbit_host,
        rabbit_port,
        rabbit_distribution_port,
        rabbit_ctl,
        logpath=rabbit_logpath,
        path=tmpdir,
        plugin_path=config["plugindir"],
        node_name=config["node"],
    )
    executor.start()
    _ACTIVE_EXECUTORS.append(executor)

    rmq_username = environ.get("TEST_RMQ_USERNAME", "test_user")
    rmq_password = environ.get("TEST_RMQ_PASSWORD", "test_password")
    rmq_vhosts = environ.get("TEST_RMQ_VHOSTS", "/test")
    executor.rabbitctl_output("add_user", rmq_username, rmq_password)
    for vhost in rmq_vhosts.split(","):
        executor.rabbitctl_output("add_vhost", vhost)
        executor.rabbitctl_output(
            "set_permissions", "-p", vhost, rmq_username, ".*", ".*", ".*"
        )

    request.cls.rmq_instance = executor
    try:
        yield executor
    finally:
        _stop_executor_quietly(executor)
        try:
            _ACTIVE_EXECUTORS.remove(executor)
        except ValueError:
            pass


def _stop_executor_quietly(executor: RabbitMqExecutor | None) -> None:
    """Best-effort teardown so a stuck broker cannot hang the session."""
    if executor is None:
        return
    try:
        if executor.running():
            executor.stop()
    except Exception:
        try:
            executor.kill(wait=False)
        except Exception:
            pass


def _arm_force_exit(exitstatus: int, grace: int) -> None:
    """Force the interpreter to exit if normal shutdown stalls.

    The watchdog runs in a daemon thread so it cannot itself prevent exit.
    If the process has not terminated within ``grace`` seconds of pytest
    finishing, we ``os._exit`` so CI sees a clean (non-timeout) result.
    """

    def _watchdog() -> None:
        time.sleep(grace)
        sys.stderr.write(
            f"\n[conftest] forcing process exit after {grace}s grace period; "
            f"normal shutdown stalled.\n"
        )
        sys.stderr.flush()
        os._exit(int(exitstatus))

    threading.Thread(
        target=_watchdog, name="conftest-force-exit", daemon=True
    ).start()


def pytest_sessionfinish(session, exitstatus):  # noqa: D401
    """Stop tracked executors and arm a hard-exit watchdog."""
    for executor in list(_ACTIVE_EXECUTORS):
        _stop_executor_quietly(executor)
    _ACTIVE_EXECUTORS.clear()
    _arm_force_exit(int(exitstatus), _FORCE_EXIT_GRACE_SECONDS)
