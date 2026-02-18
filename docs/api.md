# API

## Tools

### `list_artifactory_capabilities`

List the public method surface from the installed `dohq-artifactory` package plus bridge argument conventions.

Inputs:

- none

### `invoke_artifactory_root_method`

Invoke any public method on a root `ArtifactoryPath` object (admin/build/query level operations).

Inputs:

- `method` (str)
- `positional_args` (list[any], optional)
- `keyword_args` (dict[str, any], optional)
- `base_url` (str, optional override)
- `max_items` (int, optional, `1..10000`)

### `invoke_artifactory_path_method`

Invoke any public method on a repository/path-scoped `ArtifactoryPath` object.

Inputs:

- `repository` (str)
- `method` (str)
- `path` (str, optional)
- `positional_args` (list[any], optional)
- `keyword_args` (dict[str, any], optional)
- `base_url` (str, optional override)
- `max_items` (int, optional, `1..10000`)

### `invoke_artifactory_handle_method`

Invoke any method on an object returned by previous bridge calls.

Inputs:

- `handle_id` (str)
- `method` (str)
- `positional_args` (list[any], optional)
- `keyword_args` (dict[str, any], optional)
- `max_items` (int, optional, `1..10000`)

### `list_artifactory_handles`

List active handle IDs and summaries for bridge-created objects.

Inputs:

- none

### `drop_artifactory_handle`

Drop a previously created handle.

Inputs:

- `handle_id` (str)

### `list_artifacts`

List artifacts under a repository path.

Inputs:

- `repository` (str)
- `path` (str, optional)
- `recursive` (bool, default `false`)
- `pattern` (str, default `*`)
- `include_directories` (bool, default `true`)
- `include_stats` (bool, default `false`)
- `max_items` (int, `1..1000`, default `200`)
- `base_url` (str, optional override)

### `get_artifact_details`

Fetch stat/properties/download metadata for an artifact path.

Inputs:

- `repository` (str)
- `path` (str)
- `include_properties` (bool, default `true`)
- `include_download_stats` (bool, default `false`)
- `base_url` (str, optional override)

### `read_artifact_text`

Read text content from an artifact with a size guard.

Inputs:

- `repository` (str)
- `path` (str)
- `encoding` (str, default `utf-8`)
- `max_bytes` (int, `1..5000000`, default `200000`)
- `base_url` (str, optional override)

### `write_artifact_text`

Upload text content as an artifact.

Inputs:

- `repository` (str)
- `path` (str)
- `content` (str)
- `encoding` (str, default `utf-8`)
- `overwrite` (bool, default `false`)
- `create_parents` (bool, default `true`)
- `base_url` (str, optional override)

## Bridge Argument Encodings

Use these wrappers inside `positional_args` / `keyword_args`:

- Handle reference: `{\"__handle_id__\": \"h1\"}`
- Path reference: `{\"__path__\": {\"repository\": \"libs-release-local\", \"path\": \"com/example/app.jar\", \"base_url\": \"https://host/artifactory\"}}`
- Raw bytes: `{\"__bytes_base64__\": \"...\"}`
