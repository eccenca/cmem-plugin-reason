# cmem-plugin-reason

Perform reasoning tasks and validate OWL consistency.

[![eccenca Corporate Memory](https://img.shields.io/badge/eccenca-Corporate%20Memory-orange)](https://documentation.eccenca.com) [![workflow](https://github.com/eccenca/cmem-plugin-reason/actions/workflows/check.yml/badge.svg)](https://github.com/eccenca/cmem-plugin-reason/actions) [![pypi version](https://img.shields.io/pypi/v/cmem-plugin-reason)](https://pypi.org/project/reason) [![license](https://img.shields.io/pypi/l/cmem-plugin-reason)](https://pypi.org/project/cmem-plugin-reason)

## Development

- Run [task](https://taskfile.dev/) to see all major development tasks.
- Use [pre-commit](https://pre-commit.com/) to avoid errors before commit.
- This repository was created with [this copier template](https://github.com/eccenca/cmem-plugin-template).

## Robot

This [eccenca](https://eccenca.com) [Corporate Memory](https://documentation.eccenca.com) plugin contains workflow tasks to perform reasoning (Reason) and ontology consistency checking (Validate) using [ROBOT](http://robot.obolibrary.org/).

ROBOT is published under the [BSD 3-Clause "New" or "Revised" License](https://choosealicense.com/licenses/bsd-3-clause/).
Copyright © 2015, the authors. All rights reserved.

## Build

```
➜ task clean build
```

## Installation

```
➜ cmemc admin workspace python install dist/*.tar.gz
```

Alternatively, the _build_ and _installation_ process can be initiated with the single command:

```
➜ task deploy
```

