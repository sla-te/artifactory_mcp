from __future__ import annotations

from artifactory_mcp import server


def test_expected_tools_registered() -> None:
    names = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    assert names == {
        "list_artifactory_capabilities",
        "invoke_artifactory_root_method",
        "invoke_artifactory_path_method",
        "invoke_artifactory_handle_method",
        "list_artifactory_handles",
        "drop_artifactory_handle",
        "list_artifacts",
        "get_artifact_details",
        "read_artifact_text",
        "write_artifact_text",
    }


def test_capabilities_include_core_underlying_methods() -> None:
    capabilities = server._list_capabilities_sync()
    method_names = {method["name"] for method in capabilities["path_methods"]}
    assert "aql" in method_names
    assert "get_users" in method_names
    assert "promote_docker_image" in method_names
