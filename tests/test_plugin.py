# Copyright (C) 2024-2026 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

import conda
import pytest
from conda.exceptions import (
    PackageNotInstalledError,
    PackagesNotFoundError,
    PackagesNotFoundInChannelsError,
)
from conda.plugins.hookspec import CondaSpecs
from conda.plugins.manager import CondaPluginManager

import conda_anaconda_telemetry.hooks as hooks_module
from conda_anaconda_telemetry.hooks import conda_exception_observers
from conda_anaconda_telemetry.plugin import report_error

if TYPE_CHECKING:
    from pathlib import Path

    from conda.plugins.manager import CondaPluginManager as CondaPluginManagerType
    from pytest_mock import MockerFixture


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


def test_conda_exception_observers_registration() -> None:
    """The hookimpl yields a single observer watching for PackagesNotFoundError."""
    (observer,) = conda_exception_observers()

    assert observer.name == "conda-anaconda-telemetry"
    assert observer.hook is report_error
    assert observer.watch_for == {"PackagesNotFoundError"}


def test_report_error_disabled_plugin(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """When the plugin setting is disabled, telemetry is never touched."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", False
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundError(["numpy"]))

    telemetry_cls.assert_not_called()


def test_report_error_non_install_command(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """Telemetry is only sent for the install command."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="remove"),
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(plugin_manager, PackagesNotFoundError(["numpy"]))

    telemetry_cls.assert_not_called()


def test_report_error_happy_path(
    plugin_manager: CondaPluginManagerType,
    mocker: MockerFixture,
    mock_install_attributes: dict,
) -> None:
    """On install, telemetry is initialized and the event is sent."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="install"),
    )
    telemetry = mocker.MagicMock()
    telemetry_cls = mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    raise_and_dispatch(plugin_manager, PackagesNotFoundError(["numpy"]))

    telemetry_cls.assert_called_once()
    telemetry.initialize.assert_called_once()
    telemetry.send_event.assert_called_once_with(
        "install.pnfe", "", mock_install_attributes
    )


def test_report_error_channel_resolution_failure(
    plugin_manager: CondaPluginManagerType,
    mocker: MockerFixture,
    mock_install_attributes: dict,
) -> None:
    """A real channel-resolution failure during install sends telemetry."""
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="install"),
    )
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


def test_report_error_local_prefix_lookup_failure(
    plugin_manager: CondaPluginManagerType, mocker: MockerFixture
) -> None:
    """PackageNotInstalledError during update is excluded by the command guard.

    The exception inherits from ``PackagesNotFoundError``, so the observer
    dispatches it. This verifies that ``report_error()`` returns for ``update``
    before initializing telemetry.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="update"),
    )
    telemetry_cls = mocker.patch("conda_anaconda_telemetry.plugin.AnacondaTelemetry")

    raise_and_dispatch(
        plugin_manager, PackageNotInstalledError("/opt/conda/envs/foo", "numpy")
    )

    telemetry_cls.assert_not_called()


def test_report_error_initialize_failure_is_consumed(mocker: MockerFixture) -> None:
    """If initialize() raises, send_event is never called and nothing propagates.

    Calls report_error() directly (bypassing plugin_manager dispatch) so this test
    verifies plugin.py's own try/except, not conda's dispatch-level handling of
    observer exceptions.
    """
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context.plugins.anaconda_telemetry", True
    )
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="install"),
    )
    telemetry = mocker.MagicMock()
    telemetry.initialize.side_effect = RuntimeError("boom")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    event = SimpleNamespace(exc_type=PackagesNotFoundError)
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
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="install"),
    )
    mock_initialize = mocker.patch(
        "conda_anaconda_telemetry.otel.sig.initialize_telemetry"
    )
    mock_send_event = mocker.patch("conda_anaconda_telemetry.otel.sig.send_event")

    event = SimpleNamespace(exc_type=PackagesNotFoundError)
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
    mocker.patch(
        "conda_anaconda_telemetry.plugin.context._argparse_args",
        mocker.MagicMock(cmd="install"),
    )
    telemetry = mocker.MagicMock()
    telemetry.send_event.side_effect = RuntimeError("boom")
    mocker.patch(
        "conda_anaconda_telemetry.plugin.AnacondaTelemetry", return_value=telemetry
    )

    event = SimpleNamespace(exc_type=PackagesNotFoundError)
    report_error(event)  # must not raise

    telemetry.send_event.assert_called_once_with(
        "install.pnfe", "", mock_install_attributes
    )
