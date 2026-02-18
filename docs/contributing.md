# Contributing

## Workflow

1. Sync dependencies with `uv sync --python 3.13`.
2. Make focused changes with tests or verification commands.
3. Run:
   - `uv run --python 3.13 python -m py_compile server.py main.py src/artifactory_mcp/server.py`
   - `uv run python -m pytest -q tests/test_smoke.py`
   - `uv run pre-commit run -a`
4. Update docs (`README.md`, `HANDOFF.md`, and `docs/*`) if behavior changed.
5. Add an entry to `CHANGELOG.md` for user-facing updates.
