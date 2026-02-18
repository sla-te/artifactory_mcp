from __future__ import annotations

from artifactory import ArtifactoryException


def _format_error(action: str, exc: Exception) -> str:
    if isinstance(exc, (ValueError, FileNotFoundError, FileExistsError, TypeError)):
        return str(exc)
    if isinstance(exc, ArtifactoryException):
        message = f"Artifactory error during {action}: {exc}"
        text = str(exc)
        if "404 Client Error" in text and "/api/" in text:
            message += " Hint: use a base URL that includes '/artifactory', e.g. https://host/artifactory."
        if "Props Authentication Token not found" in text:
            message += " Hint: verify ARTIFACTORY_TOKEN is a valid full access token for this Artifactory instance."
        return message
    return f"Unexpected error during {action}: {type(exc).__name__}: {exc}"
