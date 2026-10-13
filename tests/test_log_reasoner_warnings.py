"""Tests for writing the reasoner's warnings to the task log"""

from subprocess import CompletedProcess

import pytest

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.utils import log_reasoner_warnings

WARNING = "Class inclusions may be incomplete because ontology satisfiability cannot be checked!"
INCOMPLETENESS = "Potential incompleteness due to occurrences of HasKey"
STDERR = "\n".join(
    [
        "14:42:07.900 [main] INFO  c.e.r.ReasonCommand -- Loading ontology from data.nt",
        f"14:42:07.906 [main] WARN  o.s.e.r.c.Incompleteness -- {WARNING}",
        f"14:42:07.906 [main] INFO  o.s.e.r.c.Incompleteness -- {INCOMPLETENESS}",
        "14:42:07.950 [main] INFO  c.e.r.ReasonCommand -- Done.",
        "not a log line",
    ]
).encode()


class Recorder:
    """Records the warnings logged"""

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        """Record a warning"""
        self.warnings.append(message)


def test_log_reasoner_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warnings and ELK's incompleteness lines go to the task log, other lines do not"""
    plugin = ReasonPlugin(data_graph_iri="https://example.org/data/", reasoner="elk")
    recorder = Recorder()
    monkeypatch.setattr(plugin, "log", recorder)

    log_reasoner_warnings(plugin, CompletedProcess(args=[], returncode=0, stderr=STDERR))

    assert recorder.warnings == [WARNING, INCOMPLETENESS]
