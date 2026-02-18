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
- Internal server implementation refactored into focused modules:
  - `src/artifactory_mcp/tools.py`
  - `src/artifactory_mcp/runtime.py`
  - `src/artifactory_mcp/settings.py`
  - `src/artifactory_mcp/artifactory_client.py`
  - `src/artifactory_mcp/bridge.py`
  - `src/artifactory_mcp/artifact_ops.py`
  - `src/artifactory_mcp/models.py`
  - `src/artifactory_mcp/handles.py`
- Package entrypoint added: `artifactory-mcp` and module entrypoint `python -m artifactory_mcp`.
- Documentation added (`README.md`, `docs/*`, `CHANGELOG.md`).
- Added installation docs for environments without `uv`.
- Added MCP client onboarding docs for VS Code Copilot and Codex, with both `uv` and dedicated `.venv` launch configurations.
- Full underlying package coverage now provided through generic bridge invocation and handle workflow.
- Added `examples/tool_calls.json` and `tests/test_smoke.py` for layout completeness.
- Bootstrapped pre-commit with Python profile and merged template settings into `pyproject.toml`.
- Fixed mypy hook failures by:
  - adding runtime dependencies to the pre-commit mypy hook environment.
  - adding `typings/artifactory.pyi` local stubs for untyped `dohq-artifactory` imports.
- Improved runtime validation/errors:
  - token validation now rejects header-only JWT fragments.
  - Artifactory error hints now include missing `/artifactory` base URL guidance.
  - host-only base URLs are auto-normalized to append `/artifactory`.
  - details serialization now handles non-dict objects returned by `download_stats()`.

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
- Live Artifactory validation (`https://artifactory.local/artifactory`, SSL verify disabled) with identity token:
  - All 10 MCP tools validated end-to-end:
    `list_artifactory_capabilities`,
    `invoke_artifactory_root_method`,
    `invoke_artifactory_path_method`,
    `invoke_artifactory_handle_method`,
    `list_artifactory_handles`,
    `drop_artifactory_handle`,
    `list_artifacts`,
    `get_artifact_details`,
    `read_artifact_text`,
    `write_artifact_text`.
  - Handle workflow validated using repository handles returned by `get_repositories`.
  - Limited-scope behavior validated:
    `/access/api/v1/users` returned `403 FORBIDDEN`;
    privileged/pro-only `get_users` returns expected upstream Pro limitation error.

## Known Constraints

- `dohq-artifactory` currently fails on Python 3.14 due `glob._Globber` usage upstream.
- Use Python 3.13 for this server until upstream compatibility is fixed.
- Some upstream `dohq-artifactory` methods require Artifactory Pro features and/or elevated scope; generic bridge will surface those upstream errors.

## Next Steps

1. Add integration tests against a live test Artifactory for high-risk bridge methods (`copy`, `move`, `deploy_file`, `aql`, admin entities).
2. Add policy guardrails (optional allow/deny lists) for destructive bridge methods in production.
3. Enable stricter transport security (`MCP_ENABLE_DNS_REBINDING_PROTECTION=true`) for production HTTP deployments.
