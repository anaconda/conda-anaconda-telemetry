import pytest
from typing import NamedTuple

from conda_anaconda_telemetry import metrics


class MockVirtualPackage(NamedTuple):
    name: str
    build: str
    version: str


class MockArgs(NamedTuple):
    cmd: str
    packages: tuple[str, ...]
    match_spec: str


@pytest.fixture(autouse=True)
def metrics_mocks(mocker):
    """
    Mocks that apply to all tests run here
    """
    mocker.patch(
        "conda.base.context.Context.channels",
        new_callable=mocker.PropertyMock,
        return_value=("test",)
    )
    mocker.patch(
        "conda_anaconda_telemetry.metrics.context.plugin_manager.get_virtual_package_records",
        return_value=[MockVirtualPackage(name="test_name", version="test_version", build="test_build")]
    )
    mocker.patch(
        "conda_anaconda_telemetry.metrics.all_channel_urls",
        return_value=["http://localhost/pkgs/main"]
    )
    mocker.patch(
        "conda_anaconda_telemetry.metrics.context._argparse_args",
        MockArgs(cmd="test", packages=("test", ), match_spec="test")
    )

    mocker.patch("conda_anaconda_telemetry.metrics.conda_version", "0.0.0")
    mocker.patch("conda_anaconda_telemetry.metrics.conda_build_version", "0.0.0")
    mocker.patch(
        "conda.base.context.Context.python_implementation_name_version",
        new_callable=mocker.PropertyMock,
        return_value=("CPython", "3.54.0")
    )
    mocker.patch(
        "conda_anaconda_telemetry.metrics.context.solver_user_agent",
        return_value="solver/magic 0.0.0"
    )
    mocker.patch(
        "conda.base.context.Context.platform_system_release",
        new_callable=mocker.PropertyMock,
        return_value=("Linux", "9999-generic")
    )
    mocker.patch("conda_anaconda_telemetry.metrics.list_packages", return_value=(0, ("test", )))


def test_get_virtual_packages():
    """Ensures the basic functionality of the get_virtual_packages function."""
    assert metrics.get_virtual_packages() == ("test_name=test_version=test_build", )


def test_get_channel_urls():
    """Ensures the basic functionality of the get_channel_urls function."""
    assert metrics.get_channel_urls() == ('http://localhost/pkgs/main',)


def test_get_conda_command():
    """Ensures the basic functionality of the get_conda_command function."""
    assert metrics.get_conda_command() == "test"


def test_get_package_list():
    """Ensures the basic functionality of the get_package_list function."""
    assert metrics.get_package_list() == ("test", )


def test_get_search_term():
    """Ensures the basic functionality of the get_search_term function."""
    assert metrics.get_search_term() == "test"


def test_get_install_arguments():
    """Ensures the basic functionality of the get_install_arguments function."""
    assert metrics.get_install_arguments() == ("test", )


def test_get_sys_info():
    """Ensures the basic functionality of the get_sys_info function."""
    assert metrics.get_sys_info() == metrics.SysInfo(
        conda_command="test",
        conda_build_version="0.0.0",
    )

    assert metrics.get_sys_info(extra=True) == metrics.SysInfo(
        conda_command="test",
        conda_build_version="0.0.0",
        python_implementation="CPython",
        python_version="3.54.0",
        conda_version="0.0.0",
        solver_version="solver/magic 0.0.0",
        platform_system="Linux",
        platform_release="9999-generic",
    )

