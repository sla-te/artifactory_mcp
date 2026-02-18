# Installation

## Prerequisites

- Python `3.13` available
- One of:
  - `uv` (recommended)
  - `venv` + `pip`

## Setup With `uv`

```bash
uv sync --python 3.13
```

## Setup Without `uv`

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

With `uv`:

```bash
uv run artifactory-mcp
```

Without `uv`:

```bash
artifactory-mcp
```

## Inspector

With `uv`:

```bash
uv run mcp dev server.py
```

Without `uv`:

```bash
.venv/bin/mcp dev server.py
```

## Claude Desktop Install

With `uv`:

```bash
uv run mcp install server.py --name artifactory-mcp
```

Without `uv`:

```bash
.venv/bin/mcp install server.py --name artifactory-mcp
```
