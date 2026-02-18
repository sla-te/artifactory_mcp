# Changelog

## [0.1.0] - 2026-02-18

### Added

- Initial `FastMCP` Artifactory server implementation.
- Tooling for list/details/read/write operations against JFrog Artifactory.
- Environment-driven transport options (`stdio`, `streamable-http`) and security settings.
- Project documentation and handoff notes.
- Generic bridge tools for full underlying package coverage:
  - `list_artifactory_capabilities`
  - `invoke_artifactory_root_method`
  - `invoke_artifactory_path_method`
  - `invoke_artifactory_handle_method`
  - `list_artifactory_handles`
  - `drop_artifactory_handle`
- Smoke tests with `pytest`.
- Pre-commit baseline files (`.pre-commit-config.yaml`, `.gitleaks.toml`, `.typos.toml`, `.markdownlint`, `.markdownlintignore`).

### Changed

- Expanded installation documentation with a non-`uv` path using `venv` + `pip`.
- Added MCP client setup docs for VS Code Copilot (`.vscode/mcp.json`) and Codex (`~/.codex/config.toml`), including isolated `.venv` launch examples.
- Improved bridge/runtime diagnostics:
  - clearer hints for base URL missing `/artifactory`.
  - clearer hints for invalid/partial token values.
- Hardened artifact detail serialization for non-dict `download_stats()` payloads.
- Updated coverage model from a subset-only toolset to a full-surface bridge over public `dohq-artifactory` methods.
- Reorganized project layout to `src/artifactory_mcp/` package structure.
- Refactored `src/artifactory_mcp/server.py` into focused modules
  (`tools`, `runtime`, `settings`, `artifactory_client`, `bridge`,
  `artifact_ops`, `models`, `handles`) while keeping `server.py`
  as a compatibility entrypoint.
- Added package build metadata and CLI entrypoint `artifactory-mcp`.
- Kept root `server.py` and `main.py` as compatibility wrappers.
- Updated docs to describe bridge argument encodings and full-coverage invocation model.
- Merged scaffolded Python lint/type settings into `pyproject.toml` and added `pre-commit` to dev dependencies.
- Tuned pre-commit hooks for this repo (`bandit` excludes `tests`, markdownlint ignores `AGENTS.md`).
- Fixed mypy hook reliability by:
  - installing runtime dependencies in the pre-commit mypy environment.
  - adding local `typings/artifactory.pyi` stubs for untyped `dohq-artifactory` surfaces.
