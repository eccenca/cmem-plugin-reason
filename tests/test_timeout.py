"""Tests for the reasoner's time limit and for ending it when the workflow is cancelled"""

import re
import sys
import time
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from cmem_plugin_base.testing import TestExecutionContext

from cmem_plugin_reason import utils
from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.plugin_validate import ValidatePlugin
from cmem_plugin_reason.utils import (
    REASONER,
    TIMEOUT_EXIT_CODE,
    ReasonerCancelledError,
    eccenca_reasoner,
    raise_on_error,
    run_process,
)

SLEEP = [sys.executable, "-c", "import time; time.sleep(60)"]


def test_run_process_ends_a_cancelled_process() -> None:
    """A cancelled process is ended at the next check, not run to its end"""
    start = time.monotonic()
    with pytest.raises(ReasonerCancelledError):
        run_process(SLEEP, cancelled=lambda: True)
    assert time.monotonic() - start < 30


def test_run_process_returns_the_output() -> None:
    """A process that isn't cancelled runs to its end and returns its output"""
    response = run_process(
        [
            sys.executable,
            "-c",
            "import sys, time; time.sleep(3); print('out'); print('err', file=sys.stderr)",
        ],
        cancelled=lambda: False,
    )
    assert response.returncode == 0
    assert response.stdout.strip() == b"out"
    assert response.stderr.strip() == b"err"


@pytest.mark.parametrize(("timeout", "passed"), [(0, False), (5, True)])
def test_eccenca_reasoner_passes_the_timeout(
    monkeypatch: pytest.MonkeyPatch, timeout: int, passed: bool
) -> None:
    """--timeout goes to the jar only with a limit"""
    calls = []
    monkeypatch.setattr(
        utils, "run_process", lambda cmd, cancelled: calls.append(cmd) or CompletedProcess(cmd, 0)
    )
    eccenca_reasoner(["reason", "--input", "in.nt"], 20, timeout)
    assert (calls[0][-2:] == ["--timeout", "5"]) is passed


def test_raise_on_error_names_the_time_limit() -> None:
    """The jar's exit code for --timeout gives a clear error with the limit"""
    stderr = (
        b"11:07:34.622 [eccenca-reasoner-timeout] ERROR c.e.reasoner.Watchdog -- Not finished "
        b"within the time limit of 30 minutes (--timeout); stopped."
    )
    with pytest.raises(
        OSError, match=re.escape("did not finish within the time limit of 30 minutes")
    ):
        raise_on_error(CompletedProcess([], TIMEOUT_EXIT_CODE, b"", stderr), "Reasoning")


def test_the_jar_stops_at_the_time_limit(tmp_path: Path) -> None:
    """The bundled jar stops itself with the exit code and message the plugin expects"""
    data = tmp_path / "in.ttl"
    data.write_text("<urn:a> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:b> .\n")
    response = run_process(
        [
            "java",
            "-jar",
            REASONER,
            "reason",
            "--input",
            str(data),
            "--output",
            str(tmp_path / "out.nt"),
            "--timeout",
            "0.0001",
        ]
    )
    assert response.returncode == TIMEOUT_EXIT_CODE
    with pytest.raises(
        OSError, match=re.escape("did not finish within the time limit of 0.0001 minutes")
    ):
        raise_on_error(response, "Reasoning")


@pytest.mark.parametrize("plugin_class", [ReasonPlugin, ValidatePlugin])
def test_negative_timeout_is_rejected(plugin_class: type) -> None:
    """A negative timeout is an error at execution"""
    plugin = plugin_class(timeout=-1)
    with pytest.raises(ValueError, match='Invalid value for parameter "Timeout') as exc_info:
        plugin.execute(inputs=(), context=TestExecutionContext())
    assert "Timeout (minutes)" in str(exc_info.value)
