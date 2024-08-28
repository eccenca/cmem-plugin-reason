"""doc"""

from pathlib import Path

with (Path(__path__[0]) / "reason_doc.md").open("r") as f:
    REASON_DOC = f.read()

with (Path(__path__[0]) / "validate_doc.md").open("r") as f:
    VALIDATE_DOC = f.read()
