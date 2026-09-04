from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pytest

from _tilebox.grpc.client_metadata import (
    CLIENT_HEADER,
    _architecture,
    _cloud_environment,
    _execution_environment,
    _invoker,
    _package_version,
    _serialize_dictionary,
    client_metadata,
)


def test_serializes_full_client_header() -> None:
    fields = {
        "name": "python",
        "version": "1.8.0",
        "runtime": "python",
        "runtime-version": "3.12.4",
        "os": "linux",
        "os-version": "6.8.0",
        "arch": "arm64",
        "execution-environment": "jupyter",
        "cloud-provider": "gcp",
        "cloud-platform": "gcp_cloud_run",
        "cloud-region": "europe-west1",
    }

    assert _serialize_dictionary(fields) == (
        'name="python", version="1.8.0", runtime="python", runtime-version="3.12.4", os="linux", '
        'os-version="6.8.0", arch="arm64", execution-environment="jupyter", cloud-provider="gcp", '
        'cloud-platform="gcp_cloud_run", cloud-region="europe-west1"'
    )


@patch("_tilebox.grpc.client_metadata._cloud_environment", return_value={})
@patch("_tilebox.grpc.client_metadata._invoker", return_value={})
@patch("_tilebox.grpc.client_metadata._execution_environment", return_value=None)
@patch("_tilebox.grpc.client_metadata._architecture", return_value=None)
@patch("_tilebox.grpc.client_metadata._os_name", return_value=None)
@patch("_tilebox.grpc.client_metadata.platform.release", return_value="")
@patch("_tilebox.grpc.client_metadata.platform.python_version", return_value="")
@patch("_tilebox.grpc.client_metadata._package_version", return_value="1.2.3")
def test_minimal_client_header(*_: object) -> None:
    client_metadata.cache_clear()

    assert client_metadata() == {CLIENT_HEADER: 'name="python", version="1.2.3", runtime="python"'}
    client_metadata.cache_clear()


@patch("_tilebox.grpc.client_metadata.package_version")
def test_uses_umbrella_package_version(package_version: object) -> None:
    package_version.side_effect = [PackageNotFoundError, "1.2.3"]  # ty: ignore[unresolved-attribute]

    assert _package_version() == "1.2.3"


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        ("x86_64", "amd64"),
        ("AMD64", "amd64"),
        ("i686", "386"),
        ("aarch64", "arm64"),
        ("armv7l", "arm"),
    ],
)
def test_normalizes_architecture(machine: str, expected: str) -> None:
    with patch("_tilebox.grpc.client_metadata.platform.machine", return_value=machine):
        assert _architecture() == expected


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"GITHUB_ACTIONS": "true"}, "github-actions"),
        ({"GITLAB_CI": "true"}, "gitlab-ci"),
        ({"CIRCLECI": "true"}, "circleci"),
        ({"BUILDKITE": "true"}, "buildkite"),
        ({"JENKINS_URL": "https://jenkins.example"}, "jenkins"),
        ({"TEAMCITY_VERSION": "2026.1"}, "teamcity"),
        ({"TF_BUILD": "True"}, "azure-pipelines"),
        ({"K_SERVICE": "service"}, "google-cloud-run"),
        ({"AWS_EXECUTION_ENV": "AWS_Lambda_python3.13"}, "aws-lambda"),
        (
            {"AWS_EXECUTION_ENV": "AWS_Lambda_python3.13", "FUNCTIONS_WORKER_RUNTIME": "python"},
            "aws-lambda",
        ),
        ({"FUNCTIONS_WORKER_RUNTIME": "python"}, "azure-functions"),
        ({"KUBERNETES_SERVICE_HOST": "10.0.0.1"}, "kubernetes"),
        ({"COLAB_RELEASE_TAG": "release"}, "google-colab"),
        ({"JPY_PARENT_PID": "123"}, "jupyter"),
        ({"JPY_PARENT_PID": "123", "JUPYTERLAB_DIR": "/opt/jupyterlab"}, "jupyterlab"),
        ({"GITHUB_ACTIONS": "false"}, None),
        ({}, None),
    ],
)
@patch("_tilebox.grpc.client_metadata.sys.stdin.isatty", return_value=False)
@patch("_tilebox.grpc.client_metadata._interactive_shell", return_value=None)
def test_detects_execution_environment(
    interactive_shell: object, stdin_isatty: object, environ: dict[str, str], expected: str | None
) -> None:
    _ = interactive_shell, stdin_isatty
    assert _execution_environment(environ) == expected


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, {}),
        ({"AGENT": "amp"}, {"invoker": "amp"}),
        ({"COPILOT_AGENT_SESSION_ID": "session"}, {"invoker": "github-copilot"}),
        ({"OPENCODE": "1"}, {"invoker": "opencode"}),
        ({"CLAUDECODE": "1"}, {"invoker": "claude-code"}),
        ({"CURSOR_AGENT": "1"}, {"invoker": "cursor"}),
        (
            {"CODEX_SESSION_ID": "session", "CODEX_VERSION": "1.2.3"},
            {"invoker": "codex", "invoker-version": "1.2.3"},
        ),
        ({"GEMINI_CLI": "1"}, {"invoker": "gemini-cli"}),
    ],
)
def test_detects_invoker(environ: dict[str, str], expected: dict[str, str]) -> None:
    assert _invoker(environ) == expected


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, {}),
        (
            {"AWS_EXECUTION_ENV": "AWS_Lambda_python3.13", "AWS_REGION": "eu-west-1"},
            {"cloud-provider": "aws", "cloud-platform": "aws_lambda", "cloud-region": "eu-west-1"},
        ),
        (
            {"K_SERVICE": "service", "GOOGLE_CLOUD_REGION": "europe-west1"},
            {"cloud-provider": "gcp", "cloud-platform": "gcp_cloud_run", "cloud-region": "europe-west1"},
        ),
        (
            {"WEBSITE_INSTANCE_ID": "instance", "REGION_NAME": "westeurope"},
            {"cloud-provider": "azure", "cloud-platform": "azure_app_service", "cloud-region": "westeurope"},
        ),
        (
            {"FUNCTIONS_WORKER_RUNTIME": "python", "REGION_NAME": "westeurope"},
            {"cloud-provider": "azure", "cloud-platform": "azure_functions", "cloud-region": "westeurope"},
        ),
        ({"KUBERNETES_SERVICE_HOST": "10.0.0.1"}, {}),
        (
            {
                "CLOUD_PROVIDER": "custom",
                "CLOUD_PLATFORM": "custom_platform",
                "CLOUD_REGION": "custom-region",
            },
            {},
        ),
    ],
)
def test_detects_cloud_environment(environ: dict[str, str], expected: dict[str, str]) -> None:
    assert _cloud_environment(environ) == expected


def test_omits_invalid_and_oversized_fields_and_bounds_header() -> None:
    fields = {
        "name": "python",
        "unicode": "München",
        "oversized": "x" * 257,
        **{f"field-{index}": "x" * 256 for index in range(10)},
    }

    header = _serialize_dictionary(fields)

    assert header.startswith('name="python"')
    assert "unicode" not in header
    assert "oversized" not in header
    assert len(header.encode("ascii")) <= 2 * 1024
