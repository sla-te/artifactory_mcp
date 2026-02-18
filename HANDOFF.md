# Handoff

## Current Status

- Project scaffolded with `uv`.
- Dependencies installed: `mcp[cli]`, `dohq-artifactory`; dev dependency: `pytest`.
- MCP server implementation in `src/artifactory_mcp/server.py` now exposes 10 tools:
  - `list_artifactory_capabilities`
  - `invoke_artifactory_root_method`
  - `invoke_artifactory_path_method`
  - `invoke_artifactory_handle_method`
  - `list_artifactory_handles`
  - `drop_artifactory_handle`
  - `list_artifacts`
  - `get_artifact_details`
  - `read_artifact_text`
  - `write_artifact_text`
- Root `server.py` and `main.py` retained as compatibility wrappers.
- Package entrypoint added: `artifactory-mcp` and module entrypoint `python -m artifactory_mcp`.
- Documentation added (`README.md`, `docs/*`, `CHANGELOG.md`).
- Added installation docs for environments without `uv`.
- Added MCP client onboarding docs for VS Code Copilot and Codex, with both `uv` and dedicated `.venv` launch configurations.
- Full underlying package coverage now provided through generic bridge invocation and handle workflow.
- Added `examples/tool_calls.json` and `tests/test_smoke.py` for layout completeness.
- Bootstrapped pre-commit with Python profile and merged template settings into `pyproject.toml`.

## Environment Details

- OS: Ubuntu on WSL
- Date: 2026-02-18
- Python runtime: pinned to `<3.14` because `dohq-artifactory` import fails on 3.14
- `uv` version: `0.10.2`

## Verification Results

- `uv sync --python 3.13`: completed successfully with a Python 3.13 virtual environment.
- `uv run --python 3.13 python -m py_compile server.py main.py src/artifactory_mcp/*.py tests/test_smoke.py`:
  validates src layout syntax.
- `uv run --python 3.13 python -c "from artifactory_mcp import server; print(server.SETTINGS.mcp_transport)"`: validates package import/startup wiring.
- `uv run --python 3.13 python -c "from artifactory_mcp import server; print(len(server.mcp._tool_manager.list_tools()))"`:
  validates 10 registered MCP tools including bridge tools.
- `uv run --python 3.13 python -c "from artifactory_mcp import server; cap=server._list_capabilities_sync(); print(cap['path_method_count'])"`:
  validates dynamic method discovery from underlying package.
- `uv run python -m pytest -q tests/test_smoke.py`: smoke tests pass (`2 passed`).
- `uv run pre-commit install`: installed Git pre-commit hook.
- `uv run pre-commit run -a`: all configured hooks pass.
- `timeout 3s uv run artifactory-mcp`: validates package CLI entrypoint startup.
- `MCP_TRANSPORT=streamable-http timeout 3s uv run artifactory-mcp`: validated HTTP startup and clean shutdown on timeout.
- `timeout 3s .venv/bin/python server.py`: validates non-uv wrapper execution (with venv activated or explicit venv python).

## Known Constraints

- `dohq-artifactory` currently fails on Python 3.14 due `glob._Globber` usage upstream.
- Use Python 3.13 for this server until upstream compatibility is fixed.

## Next Steps

1. Add integration tests against a live test Artifactory for high-risk bridge methods (`copy`, `move`, `deploy_file`, `aql`, admin entities).
2. Add policy guardrails (optional allow/deny lists) for destructive bridge methods in production.
3. Enable stricter transport security (`MCP_ENABLE_DNS_REBINDING_PROTECTION=true`) for production HTTP deployments.
