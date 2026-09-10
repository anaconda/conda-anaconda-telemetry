# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import conda
import pytest
from conda.exceptions import (
    DryRunExit,
    PackageNotInstalledError,
    PackagesNotFoundInChannelsError,
)
from conda.models.match_spec import MatchSpec
from conda.plugins.hookspec import CondaSpecs
from conda.plugins.manager import CondaPluginManager

import conda_anaconda_telemetry.hooks as hooks_module
import conda_anaconda_telemetry.plugin as plugin_module
from conda_anaconda_telemetry.hooks import (
    conda_exception_observers,
    conda_post_commands,
    conda_post_solves,
    conda_pre_commands,
    conda_pre_solves,
)
from conda_anaconda_telemetry.plugin import (
    capture_command,
    capture_requested_packages,
    capture_resolved_packages,
    clear_command,
    report_error,
    report_success,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from unittest.mock import MagicMock

    from conda.plugins.manager import CondaPluginManager as CondaPluginManagerType
    from pytest_mock import MockerFixture


RESOLVED_PACKAGE = "numpy=1.26.0=py311h0"


@pytest.fixture
def plugin_manager(mocker: MockerFixture) -> CondaPluginManagerType:
    """A real ``CondaPluginManager`` with only our plugin registered.

    Pattern borrowed from conda's own ``tests/plugins/test_exception_observers.py``:
    build a fresh plugin manager, register the plugin under test, and dispatch a
    *real* raised exception through ``invoke_exception_observers`` so `watch_for`
    filtering and event construction are exercised exactly as conda does it.
    """
    pm = CondaPluginManager()
    pm.add_hookspecs(CondaSpecs)
    # context.plugins.anaconda_telemetry comes from hooks.py, so it must be
    # registered too, otherwise that setting won't exist here.
    pm.register(hooks_module)
    mocker.patch("conda.plugins.manager.get_plugin_manager", return_value=pm)
    return pm


@pytest.fixture(autouse=True)
def mock_install_attributes(mocker: MockerFixture) -> dict:
    """Stub get_install_attributes() so tests don't depend on live conda state.

    get_install_attributes()'s own field-by-field correctness is tested in
    tests/test_otel.py; this file only needs to check that report_error()
    calls it and forwards the result unchanged.
    """
    attributes = {"signal.name": "install", "exception.name": "PackagesNotFoundError"}
    mocker.patch(
        "conda_anaconda_telemetry.plugin.get_install_attributes",
        return_value=attributes,
    )
    return attributes


@pytest.fixture(autouse=True)
def reset_plugin_state() -> Generator[None, None, None]:
    """This ensures that no captured command state leaks between tests."""
    clear_command()
    yield
    clear_command()


@pytest.fixture
def mock_success_attributes(mocker: MockerFixture) -> dict:
    """Stub get_success_attributes() so tests don't depend on live conda state."""
    attributes = {"command": "install", "resolved.packages": [RESOLVED_PACKAGE]}
    mocker.patch(
        "conda_anaconda_telemetry.plugin.get_success_attributes",
        return_value=attributes,
    )
    return attributes


def raise_and_dispatch(
    plugin_manager: CondaPluginManagerType, exc: BaseException
) -> None:
    """Raise ``exc`` and dispatch it through ``plugin_manager`` like conda's
    own tests do.
    """
    try:
        raise exc
    except type(exc):
        _, exc_val, exc_tb = sys.exc_info()
        plugin_manager.invoke_exception_observers(exc_val, exc_tb)


def capture_request(
    plugin_manager: CondaPluginManagerType, command: str, packages: list[str]
) -> None:
    """Run the real pre-command/pre-solve hooks for a package request."""
    plugin_manager.invoke_pre_commands(command)
    plugin_manager.invoke_pre_solves(
        frozenset(MatchSpec(p) for p in packages), frozenset()
    )


def set_success_request(command: str, resolved_packages: list[str] | None) -> None:
    """Populate the command state consumed by report_success()."""
    plugin_module.command_request.command = plugin_module.TelemetryCommand(command)
    plugin_module.command_request.requested_names = ["numpy"]
    plugin_module.command_request.channels = ["defaults"]
    plugin_module.command_request.resolved_packages = resolved_packages


def test_conda_exception_observers_registration() -> None:
    """The observer receives all exceptions so it can always clear state."""
    (observer,) = conda_exception_observers()

    assert observer.name == "conda-anaconda-telemetry"
    assert observer.hook is report_error
    assert observer.watch_for == {"BaseException"}


def test_conda_pre_commands_registration() -> None:
    """The hookimpl yields a pre-command hook for supported commands."""
    (pre_command,) = conda_pre_commands()

    assert pre_command.name == "conda-anaconda-telemetry-pre-command"
    assert pre_command.action is capture_command
    assert pre_command.run_for == {"create", "install"}


def test_conda_pre_solves_registration() -> None:
    """The hookimpl yields a single pre-solve hook."""
    (pre_solve,) = conda_pre_solves()

    assert pre_solve.name == "conda-anaconda-telemetry-pre-solve"
    assert pre_solve.action is capture_requested_packages


def test_conda_post_commands_registration() -> None:
    """The hookimpl yields a post-command hook for supported commands."""
    (post_command,) = conda_post_commands()

    assert post_command.name == "conda-anaconda-telemetry-post-command"
    assert post_command.action is report_success
    assert post_command.run_for == {"create", "install"}


def test_conda_post_solves_registration() -> None:
    """The hookimpl yields a post-solve hook for resolved packages."""
    (post_solve,) = conda_post_solves()

    assert post_solve.name == "conda-anaconda-telemetry-post-solve"
    assert post_solve.action is capture_resolved_packages


@pytest.mark.parametrize(
    ("command", "expected_command"),
    [
        ("install", plugin_module.TelemetryCommand.INSTALL),
        ("create", plugin_module.TelemetryCommand.CREATE),
        ("remove", None),
        ("update", None),
    ],
)
def test_capture_command(
    mocker: MockerFixture,
    command: str,
    expected_command: plugin_module.TelemetryCommand | None,
) -> None:
    """Only an enabled supported command is retained; stale request state is
    always cleared.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.requested_names = ["stale"]
    plugin_module.command_request.channels = ["stale"]
    plugin_module.command_request.resolved_packages = ["stale=1=0"]

    capture_command(command)

    assert plugin_module.command_request.command == expected_command
    assert plugin_module.command_request.requested_names is None
    assert plugin_module.command_request.resolved_packages is None
    if expected_command is None:
        assert plugin_module.command_request.channels is None
    else:
        assert plugin_module.command_request.channels == list(
            plugin_module.context.channels
        )


def test_capture_command_disabled_plugin(mocker: MockerFixture) -> None:
    """When telemetry is disabled, the command isn't captured."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", False
    )

    capture_command("install")

    assert plugin_module.command_request.command is None


@pytest.mark.parametrize(
    ("plugin_enabled", "captured_command", "expected_names"),
    [
        (True, plugin_module.TelemetryCommand.INSTALL, ["numpy", "python"]),
        (True, plugin_module.TelemetryCommand.CREATE, ["numpy", "python"]),
        # Not captured as supported (e.g. a solve triggered by another command,
        # since conda calls this hook unconditionally).
        (True, None, None),
        (False, plugin_module.TelemetryCommand.INSTALL, None),
    ],
)
def test_capture_requested_packages(
    mocker: MockerFixture,
    plugin_enabled: bool,
    captured_command: plugin_module.TelemetryCommand | None,
    expected_names: list[str] | None,
) -> None:
    """Pre-solve only captures normalized names for a captured, enabled
    supported command.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry",
        plugin_enabled,
    )
    plugin_module.command_request.command = captured_command

    capture_requested_packages(
        frozenset({MatchSpec("numpy"), MatchSpec("python >=3.11")}), frozenset()
    )

    assert plugin_module.command_request.requested_names == expected_names


def test_capture_resolved_packages(mocker: MockerFixture) -> None:
    """The post-solve hook stores the most recent linked package records."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    first = mocker.MagicMock(name="first")
    first.name, first.version, first.build = "numpy", "1.25.0", "py311h0"
    second = mocker.MagicMock(name="second")
    second.name, second.version, second.build = "numpy", "1.26.0", "py311h1"

    capture_resolved_packages("repodata.json", (), (first,))
    capture_resolved_packages("repodata.json", (), (second,))

    assert plugin_module.command_request.resolved_packages == ["numpy=1.26.0=py311h1"]


def test_capture_resolved_packages_records_empty_solve(mocker: MockerFixture) -> None:
    """An empty solve is captured as an empty list rather than missing state."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.CREATE

    capture_resolved_packages("repodata.json", (), ())

    assert plugin_module.command_request.resolved_packages == []


@pytest.mark.parametrize("command_name", ["install", None])
def test_clear_command_resets_state(command_name: str | None) -> None:
    """clear_command() resets all captured state regardless of its argument."""
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    plugin_module.command_request.requested_names = ["numpy"]
    plugin_module.command_request.channels = ["defaults"]
    plugin_module.command_request.resolved_packages = [RESOLVED_PACKAGE]

    clear_command(command_name)

    assert plugin_module.command_request.command is None
    assert plugin_module.command_request.requested_names is None
    assert plugin_module.command_request.channels is None
    assert plugin_module.command_request.resolved_packages is None


def test_post_commands_hook_clears_state_after_success(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """The registered post-command hook sends success and clears captured state."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    telemetry = mocker.MagicMock()
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )
    capture_request(plugin_manager, "install", ["numpy"])
    plugin_manager.invoke_post_solves("repodata.json", (), ())
    assert plugin_module.command_request.command == "install"

    plugin_manager.invoke_post_commands("install")

    telemetry.send_event.assert_called_once()
    assert plugin_module.command_request.command is None
    assert plugin_module.command_request.requested_names is None
    assert plugin_module.command_request.channels is None
    assert plugin_module.command_request.resolved_packages is None


def test_non_reportable_exception_clears_request(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """A non-reportable exception clears the captured install request."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["numpy"])
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, DryRunExit())

    telemetry_cls.assert_not_called()
    assert plugin_module.command_request.command is None
    assert plugin_module.command_request.requested_names is None


def test_report_error_disabled_plugin(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """When the plugin setting is disabled, telemetry is never touched."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", False
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundInChannelsError(["numpy"], []))

    telemetry_cls.assert_not_called()


def test_report_error_non_install_command(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Telemetry is only sent for the install and create commands."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_manager.invoke_pre_commands("remove")
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundInChannelsError(["numpy"], []))

    telemetry_cls.assert_not_called()


def test_report_error_ignores_package_not_installed(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Ensure PackageNotInstalledError does not trigger telemetry.

    It is a sibling of the tracked error class under PackagesNotFoundError.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["numpy"])
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackageNotInstalledError("/prefix", "numpy"))

    telemetry_cls.assert_not_called()


def test_report_error_unrepresentable_packages_skipped(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Telemetry is skipped when the requested packages can't be normalized."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["*"])
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundInChannelsError(["numpy"], []))

    telemetry_cls.assert_not_called()


def test_report_error_missing_attributes_skipped(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Telemetry is skipped when get_install_attributes() returns None."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["numpy"])
    mocker.patch(
        "conda_anaconda_telemetry.plugin.get_install_attributes", return_value=None
    )
    telemetry = mocker.MagicMock()
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    raise_and_dispatch(plugin_manager, PackagesNotFoundInChannelsError(["numpy"], []))

    telemetry.send_event.assert_not_called()


def test_report_error_clears_state_after_failure(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Captured state is cleared after a failure, since post-command hooks
    don't run when the command fails.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["numpy"])
    plugin_module.command_request.resolved_packages = [RESOLVED_PACKAGE]
    mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundInChannelsError(["numpy"], []))

    assert plugin_module.command_request.command is None
    assert plugin_module.command_request.requested_names is None
    assert plugin_module.command_request.channels is None
    assert plugin_module.command_request.resolved_packages is None


def test_report_error_channel_resolution_failure(
    plugin_manager: CondaPluginManagerType,
    mocker: MockerFixture,
    mock_install_attributes: dict,
) -> None:
    """A real channel-resolution failure during install sends telemetry."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "install", ["numpy"])
    telemetry = mocker.MagicMock()
    telemetry_cls = mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    raise_and_dispatch(
        plugin_manager, PackagesNotFoundInChannelsError(["numpy"], ["main-x"])
    )

    telemetry_cls.assert_called_once()
    telemetry.initialize.assert_called_once()
    telemetry.send_event.assert_called_once_with(
        "install.pnfe", "", mock_install_attributes
    )


def test_report_error_channel_resolution_failure_create(
    plugin_manager: CondaPluginManagerType,
    mocker: MockerFixture,
    mock_install_attributes: dict,
) -> None:
    """A real channel-resolution failure during create sends telemetry."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    capture_request(plugin_manager, "create", ["numpy"])
    telemetry = mocker.MagicMock()
    telemetry_cls = mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    raise_and_dispatch(
        plugin_manager, PackagesNotFoundInChannelsError(["numpy"], ["main-x"])
    )

    telemetry_cls.assert_called_once()
    telemetry.initialize.assert_called_once()
    telemetry.send_event.assert_called_once_with(
        "create.pnfe", "", mock_install_attributes
    )


def test_report_error_initialize_failure_is_consumed(mocker: MockerFixture) -> None:
    """If initialize() raises, send_event is never called and nothing propagates.

    Calls report_error() directly (bypassing plugin_manager dispatch) so this test
    verifies plugin.py's own try/except, not conda's dispatch-level handling of
    observer exceptions.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    plugin_module.command_request.requested_names = ["numpy"]
    telemetry = mocker.MagicMock()
    telemetry.initialize.side_effect = RuntimeError("boom")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    event = SimpleNamespace(
        exc_type=PackagesNotFoundInChannelsError,
        exc_value=PackagesNotFoundInChannelsError(["numpy"], []),
    )
    report_error(event)  # must not raise

    telemetry.send_event.assert_not_called()


def test_report_error_signal_payload_baseline(
    tmp_path: Path,
    mocker: MockerFixture,
    mock_install_attributes: dict,
) -> None:
    """Checks what's actually in the signal payload today.

    Only the anaconda_opentelemetry boundary is mocked, so this uses the real
    AnacondaTelemetry code. Update this test as attributes are added, changed,
    or removed, so a missing/renamed field fails here.
    """
    installer_info = {
        "name": "TestInstaller",
        "version": "1.0.0",
        "platform": "linux-64",
        "type": "sh",
    }
    (tmp_path / ".installer.info").write_text(json.dumps(installer_info))
    mocker.patch(
        "conda_anaconda_telemetry.resource_attributes.context",
        mocker.MagicMock(
            root_prefix=str(tmp_path),
            plugins=SimpleNamespace(anaconda_telemetry=True),
        ),
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    plugin_module.command_request.requested_names = ["numpy"]
    mock_initialize = mocker.patch(
        "conda_anaconda_telemetry.otel.sig.initialize_telemetry"
    )
    mock_send_event = mocker.patch("conda_anaconda_telemetry.otel.sig.send_event")

    event = SimpleNamespace(
        exc_type=PackagesNotFoundInChannelsError,
        exc_value=PackagesNotFoundInChannelsError(["numpy"], []),
    )
    report_error(event)

    mock_initialize.assert_called_once()
    assert mock_initialize.call_args.kwargs["signal_types"] == ["logging"]

    resource_attributes = mock_initialize.call_args.kwargs["attributes"]
    attributes = resource_attributes._get_attributes()

    # Check exact key set, this implies that if the SDK silently adds/removes a
    # field, or our code dropping one, fails this test.
    expected_keys = {
        "service_name",
        "service_version",
        "os_type",
        "os_version",
        "python_version",
        "hostname",
        "platform",
        "environment",
        "user_id",
        "client_sdk_version",
        "schema_version",
        "parameters",
        "aau.version",
        "aau.client.token",
        "aau.session.token",
        "aau.environment.token",
        "aau.organization.tokens",
        "aau.installer.tokens",
        "aau.machine.tokens",
        "installer.name",
        "installer.version",
        "installer.platform",
        "conda.version",
        "conda.ci_detected",
    }
    assert attributes.keys() - {"aau.anaconda_auth.token"} == expected_keys
    # Only spot-checking two values here; the other attributes are already
    # covered by resource_attributes.py's own tests.
    assert attributes["conda.version"] == conda.__version__
    assert attributes["installer.name"] == "TestInstaller"

    mock_send_event.assert_called_once_with(
        event_name="install.pnfe", body="", attributes=mock_install_attributes
    )


def test_report_error_send_event_failure_is_consumed(
    mocker: MockerFixture, mock_install_attributes: dict
) -> None:
    """If send_event() raises, the failure is consumed rather than propagating."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    plugin_module.command_request.command = plugin_module.TelemetryCommand.INSTALL
    plugin_module.command_request.requested_names = ["numpy"]
    telemetry = mocker.MagicMock()
    telemetry.send_event.side_effect = RuntimeError("boom")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    event = SimpleNamespace(
        exc_type=PackagesNotFoundInChannelsError,
        exc_value=PackagesNotFoundInChannelsError(["numpy"], []),
    )
    report_error(event)  # must not raise

    telemetry.send_event.assert_called_once_with(
        "install.pnfe", "", mock_install_attributes
    )


def test_report_success_disabled_plugin(mocker: MockerFixture) -> None:
    """When the plugin setting is disabled, telemetry is never touched."""
    set_success_request("install", [RESOLVED_PACKAGE])
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", False
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    report_success("install")

    telemetry_cls.assert_not_called()
    assert plugin_module.command_request.command is None


def test_report_success_without_post_solve_is_skipped(mocker: MockerFixture) -> None:
    """A command without captured post-solve state sends no success event."""
    set_success_request("install", None)
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    attributes = mocker.patch("conda_anaconda_telemetry.plugin.get_success_attributes")
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    report_success("install")

    attributes.assert_not_called()
    telemetry_cls.assert_not_called()
    assert plugin_module.command_request.command is None


def test_report_success_initialize_failure_is_consumed(mocker: MockerFixture) -> None:
    """If initialize() raises, send_event is never called and nothing propagates."""
    set_success_request("install", [RESOLVED_PACKAGE])
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.get_success_attributes", return_value={}
    )
    telemetry = mocker.MagicMock()
    telemetry.initialize.side_effect = RuntimeError("error")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    report_success("install")  # must not raise

    telemetry.send_event.assert_not_called()


def test_report_success_attribute_gathering_failure_is_consumed(
    mocker: MockerFixture,
) -> None:
    """If get_success_attributes() raises, telemetry is never touched."""
    set_success_request("install", [RESOLVED_PACKAGE])
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.get_success_attributes",
        side_effect=RuntimeError("error"),
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    report_success("install")  # must not raise

    telemetry_cls.assert_not_called()


def test_report_success_send_event_failure_is_consumed(
    mocker: MockerFixture, mock_success_attributes: dict
) -> None:
    """If send_event() raises, the failure is consumed rather than propagating."""
    set_success_request("install", [RESOLVED_PACKAGE])
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    telemetry = mocker.MagicMock()
    telemetry.send_event.side_effect = RuntimeError("error")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    report_success("install")  # must not raise

    telemetry.send_event.assert_called_once_with(
        "install.success", "", mock_success_attributes
    )


@pytest.mark.parametrize(
    ("command", "resolved_packages"),
    [
        ("install", [RESOLVED_PACKAGE]),
        ("create", [RESOLVED_PACKAGE]),
        ("install", []),
    ],
)
def test_report_success_sends_event(
    mocker: MockerFixture,
    mock_success_attributes: dict,
    command: str,
    resolved_packages: list[str],
) -> None:
    """A captured install/create solve emits success, including an empty solve."""
    set_success_request(command, resolved_packages)
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    telemetry = mocker.MagicMock()
    telemetry_cls = mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    report_success(command)

    telemetry_cls.assert_called_once()
    telemetry.initialize.assert_called_once()
    # Need to cast to MagicMock below to satisfy pre-commit
    cast("MagicMock", plugin_module.get_success_attributes).assert_called_once_with(
        command=command,
        channels=["defaults"],
        requested_names=["numpy"],
        resolved_packages=resolved_packages,
    )
    telemetry.send_event.assert_called_once_with(
        f"{command}.success", "", mock_success_attributes
    )
    assert plugin_module.command_request.command is None
