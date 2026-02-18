# Configuration

## Artifactory Variables

- `ARTIFACTORY_BASE_URL`: Example `https://host/artifactory`
- `ARTIFACTORY_USERNAME`: Username for basic auth
- `ARTIFACTORY_PASSWORD`: Password or API key paired with username
- `ARTIFACTORY_API_KEY`: Alternative API key auth
- `ARTIFACTORY_TOKEN`: Alternative access token auth
- `ARTIFACTORY_VERIFY_SSL`: `true|false` (default `true`)
- `ARTIFACTORY_TIMEOUT_SECONDS`: default `30`
- `ARTIFACTORY_USE_SAAS_PATH`: `true` to use `ArtifactorySaaSPath`

Only one auth method is allowed at once.

## MCP Transport Variables

- `MCP_TRANSPORT`: `stdio` or `streamable-http`
- `MCP_HOST`: HTTP host (default `127.0.0.1`)
- `MCP_PORT`: HTTP port (default `8000`)
- `MCP_STREAMABLE_HTTP_PATH`: default `/mcp`
- `MCP_STATELESS_HTTP`: `true|false`
- `MCP_JSON_RESPONSE`: `true|false`
- `MCP_LOG_LEVEL`: `DEBUG|INFO|WARNING|ERROR|CRITICAL`
- `MCP_ENABLE_DNS_REBINDING_PROTECTION`: `true|false`
- `MCP_ALLOWED_HOSTS`: comma-separated host allowlist
- `MCP_ALLOWED_ORIGINS`: comma-separated origin allowlist
- `MCP_DEFAULT_MAX_ITEMS`: default serialization limit for generic bridge tools (default `200`)
