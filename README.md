# Artifactory MCP Server

MCP server for JFrog Artifactory built with Python, `FastMCP`, and `dohq-artifactory`.

## Features

- List artifacts in a repository path with filtering and recursion.
- Fetch artifact metadata, properties, and optional download stats.
- Read text artifacts with a configurable size guard.
- Upload text artifacts with overwrite and parent-directory controls.
- Expose the full public `dohq-artifactory` method surface through generic invocation tools.
- Support handle-based follow-up calls for objects returned by admin/build/search operations.
- Run over `stdio` (local) or `streamable-http` (remote) transport.

## Architecture

- `src/artifactory_mcp/server.py`: compatibility entrypoint and public re-exports.
- `src/artifactory_mcp/tools.py`: MCP tool registrations and async tool handlers.
- `src/artifactory_mcp/runtime.py`: `FastMCP` construction, transport security, and logging.
- `src/artifactory_mcp/settings.py`: environment parsing, validation, and runtime settings.
- `src/artifactory_mcp/artifactory_client.py`: Artifactory client/path construction helpers.
- `src/artifactory_mcp/bridge.py`: generic method bridge, argument decoding, and serialization.
- `src/artifactory_mcp/artifact_ops.py`: artifact list/details/read/write sync operations.
- `src/artifactory_mcp/models.py`: shared structured output `TypedDict` models.
- `src/artifactory_mcp/handles.py`: in-memory handle store for bridge follow-up calls.
- `server.py` and `main.py`: compatibility wrappers for direct script execution.
- `src/artifactory_mcp/__main__.py`: `python -m artifactory_mcp` entrypoint.
- `docs/`: installation/configuration/API reference.
- `tests/`: verification scaffolding.
- `examples/`: reusable tool payload examples.
- `HANDOFF.md`: current project status and verification log.

## Stack

- Python `3.13` (recommended; library compatibility constraint is `<3.14`)
- `mcp[cli]` `>=1.26.0`
- `dohq-artifactory` `>=1.0.1`
- `uv` for dependency and environment management

## Quick Start

```bash
uv sync --python 3.13
```

Set authentication and Artifactory URL (choose one auth method):

```bash
export ARTIFACTORY_BASE_URL="https://your-company.jfrog.io/artifactory"
export ARTIFACTORY_USERNAME="your-user"
export ARTIFACTORY_PASSWORD="your-password-or-api-key"
```

Run locally via stdio:

```bash
uv run artifactory-mcp
```

## Install Without `uv`

Create and activate a virtual environment, then install dependencies with `pip`:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run the server:

```bash
artifactory-mcp
```

Run as streamable HTTP:

```bash
MCP_TRANSPORT=streamable-http MCP_HOST=0.0.0.0 MCP_PORT=8000 uv run artifactory-mcp
```

HTTP endpoint:

```text
http://localhost:8000/mcp
```

## MCP Inspector

```bash
uv run mcp dev server.py
```

Without `uv`:

```bash
.venv/bin/mcp dev server.py
```

## Install in Claude Desktop

```bash
uv run mcp install server.py --name artifactory-mcp \
  -v ARTIFACTORY_BASE_URL=https://your-company.jfrog.io/artifactory \
  -v ARTIFACTORY_USERNAME=your-user \
  -v ARTIFACTORY_PASSWORD=your-password-or-api-key
```

Without `uv`:

```bash
.venv/bin/mcp install server.py --name artifactory-mcp \
  -v ARTIFACTORY_BASE_URL=https://your-company.jfrog.io/artifactory \
  -v ARTIFACTORY_USERNAME=your-user \
  -v ARTIFACTORY_PASSWORD=your-password-or-api-key
```

## Add to VS Code Copilot (MCP)

Create `.vscode/mcp.json` in this repository.

If you use `uv`:

```json
{
  "servers": {
    "artifactory-mcp": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "artifactory-mcp"],
      "cwd": "${workspaceFolder}",
      "env": {
        "ARTIFACTORY_BASE_URL": "https://your-company.jfrog.io/artifactory",
        "ARTIFACTORY_USERNAME": "your-user",
        "ARTIFACTORY_PASSWORD": "your-password-or-api-key"
      }
    }
  }
}
```

If you do not use `uv` and want a dedicated `.venv` for VS Code MCP:

```bash
python3.13 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -e .
```

Then use:

```json
{
  "servers": {
    "artifactory-mcp": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "artifactory_mcp"],
      "cwd": "${workspaceFolder}",
      "env": {
        "ARTIFACTORY_BASE_URL": "https://your-company.jfrog.io/artifactory",
        "ARTIFACTORY_USERNAME": "your-user",
        "ARTIFACTORY_PASSWORD": "your-password-or-api-key"
      }
    }
  }
}
```

Windows `command` path variant:

```text
${workspaceFolder}\\.venv\\Scripts\\python.exe
```

After saving `mcp.json`, start the server from the CodeLens "Start" action and use Copilot Chat in Agent mode.

## Add to Codex

Codex reads MCP servers from `~/.codex/config.toml` (or project-local `.codex/config.toml`).

Using `uv`:

```toml
[mcp_servers.artifactory_mcp]
command = "uv"
args = ["run", "artifactory-mcp"]
cwd = "/absolute/path/to/artifactory_mcp"
startup_timeout_sec = 20

[mcp_servers.artifactory_mcp.env]
ARTIFACTORY_BASE_URL = "https://your-company.jfrog.io/artifactory"
ARTIFACTORY_USERNAME = "your-user"
ARTIFACTORY_PASSWORD = "your-password-or-api-key"
```

Without `uv`, using a dedicated venv:

```toml
[mcp_servers.artifactory_mcp]
command = "/absolute/path/to/artifactory_mcp/.venv/bin/python"
args = ["-m", "artifactory_mcp"]
cwd = "/absolute/path/to/artifactory_mcp"
startup_timeout_sec = 20

[mcp_servers.artifactory_mcp.env]
ARTIFACTORY_BASE_URL = "https://your-company.jfrog.io/artifactory"
ARTIFACTORY_USERNAME = "your-user"
ARTIFACTORY_PASSWORD = "your-password-or-api-key"
```

References:

- GitHub Copilot MCP setup: <https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/extend-copilot-chat-with-mcp>
- Codex MCP config: <https://developers.openai.com/codex/mcp>

## Tool Examples

List a repository path:

```json
{
  "repository": "libs-release-local",
  "path": "com/example",
  "recursive": true,
  "pattern": "*.jar",
  "max_items": 100
}
```

Discover available underlying methods:

```json
{}
```

Use it with tool: `list_artifactory_capabilities`

Invoke a root-level underlying method (example: list repositories):

```json
{
  "method": "get_repositories",
  "keyword_args": {
    "lazy": true
  },
  "max_items": 200
}
```

Use it with tool: `invoke_artifactory_root_method`

Read a text artifact:

```json
{
  "repository": "generic-local",
  "path": "configs/app.yaml",
  "max_bytes": 100000
}
```

Write a text artifact:

```json
{
  "repository": "generic-local",
  "path": "notes/release.txt",
  "content": "release 2026-02-18",
  "overwrite": false
}
```

## Configuration

Core settings:

- `ARTIFACTORY_BASE_URL`: base URL like `https://host/artifactory`
- `ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD`: username/password auth
- `ARTIFACTORY_API_KEY`: API key auth (alternative)
- `ARTIFACTORY_TOKEN`: access token auth (alternative)
- `ARTIFACTORY_VERIFY_SSL`: `true|false` (default `true`)
- `ARTIFACTORY_TIMEOUT_SECONDS`: request timeout (default `30`)
- `ARTIFACTORY_USE_SAAS_PATH`: use `ArtifactorySaaSPath` (default `false`)

Transport settings:

- `MCP_TRANSPORT`: `stdio` (default) or `streamable-http`
- `MCP_HOST`: HTTP bind host (default `127.0.0.1`)
- `MCP_PORT`: HTTP bind port (default `8000`)
- `MCP_STREAMABLE_HTTP_PATH`: endpoint path (default `/mcp`)
- `MCP_STATELESS_HTTP`: `true|false` (default `false`)
- `MCP_JSON_RESPONSE`: `true|false` (default `false`)
- `MCP_ENABLE_DNS_REBINDING_PROTECTION`: `true|false` (default `false`)
- `MCP_ALLOWED_HOSTS`: comma-separated host allowlist for transport security
- `MCP_ALLOWED_ORIGINS`: comma-separated origin allowlist for transport security
- `MCP_DEFAULT_MAX_ITEMS`: default max serialized items for bridge tools (default `200`)

## Validation

```bash
uv run --python 3.13 python -m py_compile server.py main.py src/artifactory_mcp/server.py
uv run python -m pytest -q tests/test_smoke.py
uv run prek -a
```

## Pre-Commit

This repo includes a Python profile pre-commit baseline with:

- `.pre-commit-config.yaml`
- `.gitleaks.toml`
- `.typos.toml`
- `.markdownlint`
- `.markdownlintignore`

Install hooks:

```bash
uv run prek install
```

## Troubleshooting

- `module 'glob' has no attribute '_Globber'`:
  - Use Python `<3.14` (for example, `uv sync --python 3.13`).
- Authentication failures:
  - Configure exactly one auth method: token, API key, or username/password.
  - `ARTIFACTORY_TOKEN` must be a complete token value. Header-only JWT fragments are rejected.
- Empty `ARTIFACTORY_BASE_URL` errors:
  - Set `ARTIFACTORY_BASE_URL` or pass `base_url` in tool calls.
- 404 errors for `/api/*` calls:
  - Use a base URL that includes `/artifactory` (for example, `https://host/artifactory`).
- Admin/user-management method errors:
  - Some methods in the underlying client require Artifactory Pro or elevated scopes and may fail on OSS/limited tokens.

## Changelog Lite

- `0.1.0` (2026-02-18): Initial MCP server with Artifactory list/details/read/write tools and stdio/HTTP transport support.

## Coverage vs `devopshq/artifactory`

Yes. The server now uses two layers:

- Typed convenience tools for common artifact workflows.
- Generic bridge tools that invoke public methods from the underlying package:
  - `list_artifactory_capabilities`
  - `invoke_artifactory_root_method`
  - `invoke_artifactory_path_method`
  - `invoke_artifactory_handle_method`
  - `list_artifactory_handles`
  - `drop_artifactory_handle`

This allows using full package features through structured method invocation:
AQL, admin entities, builds, docker promotion, copy/move/delete, properties, and checksum operations.

Bridge argument encoding conventions:

- Handle reference: `{\"__handle_id__\": \"h1\"}`
- Path reference: `{\"__path__\": {\"repository\": \"libs-release-local\", \"path\": \"com/example/app.jar\", \"base_url\": \"https://host/artifactory\"}}`
- Raw bytes: `{\"__bytes_base64__\": \"...\"}`
