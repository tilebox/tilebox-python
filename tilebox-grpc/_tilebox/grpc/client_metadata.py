import builtins
import os
import platform
import sys
from collections.abc import Mapping
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

CLIENT_HEADER = "Tilebox-Client"

_MAX_FIELD_BYTES = 256
_MAX_HEADER_BYTES = 2 * 1024


@lru_cache(maxsize=1)
def client_metadata() -> dict[str, str]:
    """Return cached metadata identifying this SDK and its execution context."""
    return {CLIENT_HEADER: _client_header()}


def _client_header() -> str:
    fields = {
        "name": "python",
        "version": _package_version(),
        "runtime": "python",
        "runtime-version": platform.python_version(),
        "os": _os_name(),
        "os-version": platform.release(),
        "arch": _architecture(),
        "execution-environment": _execution_environment(os.environ),
        **_invoker(os.environ),
        **_cloud_environment(os.environ),
    }
    return _serialize_dictionary(fields)


def _package_version() -> str | None:
    try:
        return package_version("tilebox-python")
    except PackageNotFoundError:
        try:
            return package_version("tilebox-grpc")
        except PackageNotFoundError:
            return None


def _os_name() -> str | None:
    return platform.system().lower() or None


def _architecture() -> str | None:
    machine = platform.machine().lower()
    architectures = {
        "aarch64": "arm64",
        "amd64": "amd64",
        "arm64": "arm64",
        "armv6l": "arm",
        "armv7l": "arm",
        "i386": "386",
        "i686": "386",
        "x86": "386",
        "x86_64": "amd64",
    }
    return architectures.get(machine, machine or None)


def _execution_environment(environ: Mapping[str, str]) -> str | None:
    signals = (
        (environ.get("GITHUB_ACTIONS") == "true", "github-actions"),
        (environ.get("GITLAB_CI") == "true", "gitlab-ci"),
        (_env_set(environ, "BUILDKITE"), "buildkite"),
        (_env_set(environ, "CIRCLECI"), "circleci"),
        (_env_set(environ, "JENKINS_URL"), "jenkins"),
        (_env_set(environ, "TEAMCITY_VERSION"), "teamcity"),
        (_env_set(environ, "TF_BUILD"), "azure-pipelines"),
        (_env_set(environ, "K_SERVICE", "CLOUD_RUN_JOB"), "google-cloud-run"),
        (environ.get("AWS_EXECUTION_ENV", "").startswith("AWS_Lambda_"), "aws-lambda"),
        (_env_set(environ, "FUNCTIONS_WORKER_RUNTIME"), "azure-functions"),
        (_env_set(environ, "KUBERNETES_SERVICE_HOST"), "kubernetes"),
    )
    environment = next((name for detected, name in signals if detected), None)

    if environment is not None:
        return environment

    shell = _interactive_shell()
    if _env_set(environ, "COLAB_RELEASE_TAG") or shell == "google-colab":
        environment = "google-colab"
    elif shell == "jupyter" or _env_set(environ, "JPY_PARENT_PID"):
        jupyterlab_variables = ("JUPYTERLAB_DIR", "JUPYTERLAB_SETTINGS_DIR", "JUPYTERLAB_WORKSPACES_DIR")
        environment = "jupyterlab" if _env_set(environ, *jupyterlab_variables) else "jupyter"
    elif shell == "terminal" or hasattr(sys, "ps1") or (sys.stdin is not None and sys.stdin.isatty()):
        environment = "terminal"
    return environment


def _interactive_shell() -> str | None:
    get_ipython = getattr(builtins, "get_ipython", None)
    if not callable(get_ipython):
        return None
    shell = get_ipython()
    shell_type = type(shell)
    qualified_name = f"{shell_type.__module__}.{shell_type.__name__}".lower()
    if "google.colab" in qualified_name:
        return "google-colab"
    if "zmqinteractiveshell" in qualified_name:
        return "jupyter"
    if "terminalinteractiveshell" in qualified_name:
        return "terminal"
    return None


def _invoker(environ: Mapping[str, str]) -> dict[str, str]:
    invoker = None
    version = None
    if environ.get("AGENT") == "amp":
        invoker = "amp"
    elif _env_set(environ, "COPILOT_AGENT_SESSION_ID"):
        invoker = "github-copilot"
    elif environ.get("OPENCODE") == "1":
        invoker = "opencode"
    elif _env_set(environ, "CLAUDECODE"):
        invoker = "claude-code"
    elif _env_set(environ, "CURSOR_AGENT"):
        invoker = "cursor"
    elif _env_set(environ, "CODEX_SESSION_ID", "CODEX_THREAD_ID"):
        invoker = "codex"
        version = environ.get("CODEX_VERSION")
    elif _env_set(environ, "GEMINI_CLI"):
        invoker = "gemini-cli"
    return _optional_version(invoker, version) if invoker else {}


def _optional_version(invoker: str, version: str | None) -> dict[str, str]:
    metadata = {"invoker": invoker}
    if version:
        metadata["invoker-version"] = version
    return metadata


def _cloud_environment(environ: Mapping[str, str]) -> dict[str, str]:
    provider, platform_name, region = _detect_cloud_environment(environ)
    return {
        key: value
        for key, value in (
            ("cloud-provider", provider),
            ("cloud-platform", platform_name),
            ("cloud-region", region),
        )
        if value
    }


def _detect_cloud_environment(environ: Mapping[str, str]) -> tuple[str | None, str | None, str | None]:
    if _env_set(environ, "AWS_EXECUTION_ENV", "AWS_REGION", "AWS_DEFAULT_REGION"):
        execution_environment = environ.get("AWS_EXECUTION_ENV", "")
        platform_name = None
        if execution_environment.startswith("AWS_Lambda_"):
            platform_name = "aws_lambda"
        elif execution_environment.startswith("AWS_ECS_"):
            platform_name = "aws_ecs"
        return "aws", platform_name, _first_environment_value(environ, "AWS_REGION", "AWS_DEFAULT_REGION")

    if _env_set(environ, "K_SERVICE", "CLOUD_RUN_JOB", "GAE_ENV"):
        platform_name = "gcp_cloud_run" if _env_set(environ, "K_SERVICE", "CLOUD_RUN_JOB") else "gcp_app_engine"
        region = _first_environment_value(environ, "GOOGLE_CLOUD_REGION", "CLOUD_RUN_REGION", "FUNCTION_REGION")
        return "gcp", platform_name, region

    if _env_set(environ, "WEBSITE_INSTANCE_ID", "FUNCTIONS_WORKER_RUNTIME", "REGION_NAME"):
        platform_name = None
        if _env_set(environ, "FUNCTIONS_WORKER_RUNTIME"):
            platform_name = "azure_functions"
        elif _env_set(environ, "WEBSITE_INSTANCE_ID"):
            platform_name = "azure_app_service"
        return "azure", platform_name, environ.get("REGION_NAME")

    return None, None, None


def _env_set(environ: Mapping[str, str], *names: str) -> bool:
    return any(environ.get(name) for name in names)


def _first_environment_value(environ: Mapping[str, str], *names: str) -> str | None:
    return next((value for name in names if (value := environ.get(name))), None)


def _serialize_dictionary(fields: Mapping[str, str | None]) -> str:
    members: list[str] = []
    header_size = 0
    for key, value in fields.items():
        if not value or not _valid_string(value):
            continue
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        member = f'{key}="{escaped}"'
        member_size = len(member.encode("ascii")) + (2 if members else 0)
        if header_size + member_size > _MAX_HEADER_BYTES:
            continue
        members.append(member)
        header_size += member_size
    return ", ".join(members)


def _valid_string(value: str) -> bool:
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return len(encoded) <= _MAX_FIELD_BYTES and all(0x20 <= byte <= 0x7E for byte in encoded)
