# cmem-plugin-reason

Perform reasoning tasks and validate OWL consistency.

[![eccenca Corporate Memory][cmem-shield]][cmem-link][![workflow](https://github.com/eccenca/cmem-plugin-reason/actions/workflows/check.yml/badge.svg)](https://github.com/eccenca/cmem-plugin-reason/actions) [![pypi version](https://img.shields.io/pypi/v/cmem-plugin-reason)](https://pypi.org/project/cmem-plugin-reason) [![license](https://img.shields.io/pypi/l/cmem-plugin-reason)](https://pypi.org/project/cmem-plugin-reason)
[![uv][uv-shield]][uv-link] [![ruff][ruff-shield]][ruff-link] [![mypy][mypy-shield]][mypy-link] [![copier][copier-shield]][copier] 

## Development

- Run [task](https://taskfile.dev/) to see all major development tasks.
- Commands run inside the project environment with `uv run`; to enter it
  instead, activate it with `source .venv/bin/activate` (`.venv\Scripts\activate` on Windows).
- Commit `uv.lock`: the pipeline sets `UV_LOCKED`, so it fails without it.
- Use [pre-commit](https://pre-commit.com/) to avoid errors before commit.
- The plugin runs `cmem_plugin_reason/eccenca-reasoner.jar`, scanned together with its SBOM
  `eccenca-reasoner.cdx.json` in the project root. Neither is in git: copy both from an
  eccenca-reasoner build of its `develop` branch, which uses HermiT 1.4.5.519 and JFact 5.0.3
  from Maven Central; the documentation of the reasoners and the test fixtures assume it.
- Agent instructions and skills for this project are in `.claude/` - your own
  instructions belong in `CLAUDE.md`, which is never overwritten.
- This repository was created with [this copier template](https://github.com/eccenca/cmem-plugin-template).

[cmem-link]: https://documentation.eccenca.com
[cmem-shield]: https://img.shields.io/endpoint?url=https://documentation.eccenca.com/latest/badge.json
[uv-link]: https://docs.astral.sh/uv/
[uv-shield]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
[ruff-link]: https://docs.astral.sh/ruff/
[ruff-shield]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&label=Code%20Style
[mypy-link]: https://mypy-lang.org/
[mypy-shield]: https://www.mypy-lang.org/static/mypy_badge.svg
[copier]: https://copier.readthedocs.io/
[copier-shield]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json
