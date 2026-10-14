# Copyright (C) 2024 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from conda.models.channel import Channel
from conda.models.match_spec import MatchSpec
from conda.models.records import PackageRecord

from conda_anaconda_telemetry import hooks
from conda_anaconda_telemetry.plugin import (
    capture_command,
    capture_requested_packages,
    clear_command,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

PUBLIC_CHANNEL = "https://repo.anaconda.com/pkgs/main"
FORGE_CHANNEL = "https://conda.anaconda.org/conda-forge"
PRIVATE_CHANNEL = "https://private.example.test/internal-channel"


def clear_header_caches() -> None:
    for collector in (
        hooks.get_sys_info_header_value,
        hooks.get_channel_urls_header_value,
        hooks.get_virtual_packages_header_value,
        hooks.get_installed_packages_header_value,
    ):
        cast("Any", collector).__wrapped__.cache_clear()


@pytest.fixture(autouse=True)
def header_context(mocker: MockerFixture) -> Iterator[MagicMock]:
    """Use synthetic channels and records, independent of local configuration."""
    public_channel = Channel(
        scheme="https", location="repo.anaconda.com", name="pkgs/main"
    )
    properties = {
        "channels": (PUBLIC_CHANNEL,),
        "subdir": "linux-64",
        "subdirs": ("linux-64", "noarch"),
        "channel_alias": Channel(
            scheme="https", location="conda.anaconda.org", name=""
        ),
        "custom_channels": {},
        "custom_multichannels": {"defaults": (public_channel,)},
        "migrated_channel_aliases": (),
        "migrated_custom_channels": {},
    }
    for name, value in properties.items():
        mocker.patch(
            f"conda.base.context.Context.{name}",
            new_callable=mocker.PropertyMock,
            return_value=value,
        )
    mocker.patch.object(hooks.context.plugins, "anaconda_telemetry", True)
    mocker.patch.object(
        hooks.context.plugin_manager, "get_virtual_package_records", return_value=()
    )
    mocker.patch.object(
        hooks.context,
        "_argparse_args",
        SimpleNamespace(cmd="install", packages=[], match_spec="public-package"),
    )
    prefix_data = mocker.patch("conda_anaconda_telemetry.hooks.PrefixData")
    prefix_data.return_value.iter_records.return_value = ()
    mocker.patch.object(MatchSpec, "_MATCHER_CACHE", {})
    mocker.patch("conda.models.match_spec._PARSE_CACHE", {})
    Channel._reset_state()
    clear_command()
    clear_header_caches()
    yield prefix_data
    clear_command()
    clear_header_caches()
    Channel._reset_state()


def set_channels(mocker: MockerFixture, *channels: str) -> None:
    mocker.patch(
        "conda.base.context.Context.channels",
        new_callable=mocker.PropertyMock,
        return_value=channels,
    )
    Channel._reset_state()


def package_record(name: str, channel: str | Channel) -> PackageRecord:
    return PackageRecord(
        name=name,
        version="1.0",
        build="0",
        build_number=0,
        channel=channel,
        subdir="linux-64",
    )


def emitted_headers() -> dict[str, str]:
    return {
        header.name: header.value
        for header in hooks.conda_request_headers("repo.anaconda.com", "/pkgs/main")
    }


def capture_specs(*specs: str) -> None:
    capture_command("install")
    capture_requested_packages(frozenset(map(MatchSpec, specs)), frozenset())


def test_public_header_values(mocker: MockerFixture, header_context: MagicMock) -> None:
    set_channels(mocker, PUBLIC_CHANNEL, FORGE_CHANNEL)
    header_context.return_value.iter_records.return_value = (
        package_record("z-public", FORGE_CHANNEL),
        package_record("a-public", PUBLIC_CHANNEL),
    )
    capture_specs("defaults::a-public=1.0=0", "conda-forge::z-public")

    headers = emitted_headers()

    assert headers[hooks.HEADER_CHANNELS].split(hooks.FIELD_SEPARATOR) == [
        f"{PUBLIC_CHANNEL}/linux-64",
        f"{PUBLIC_CHANNEL}/noarch",
        f"{FORGE_CHANNEL}/linux-64",
        f"{FORGE_CHANNEL}/noarch",
    ]
    assert headers[hooks.HEADER_PACKAGES] == (
        "defaults/linux-64::a-public-1.0-0;conda-forge/linux-64::z-public-1.0-0"
    )
    assert set(headers[hooks.HEADER_INSTALL].split(hooks.FIELD_SEPARATOR)) == {
        "a-public",
        "z-public",
    }


@pytest.mark.parametrize(
    "private_channel",
    [
        PRIVATE_CHANNEL,
        "https://private-user:private-password@private.example.test/internal-channel",
        "https://private.example.test/t/private-token/internal-channel",
        "https://conda.anaconda.org/private-organization",
        "https://repo.anaconda.com/pkgs/main/private-project",
        "file:///synthetic-private/channel",
    ],
)
def test_private_data_absent_from_emitted_headers(
    mocker: MockerFixture, header_context: MagicMock, private_channel: str
) -> None:
    set_channels(mocker, PUBLIC_CHANNEL, private_channel)
    header_context.return_value.iter_records.return_value = (
        package_record("public-package", PUBLIC_CHANNEL),
        package_record("private-package", private_channel),
    )
    capture_specs("defaults::public-package", "private-request")

    headers = emitted_headers()

    assert headers[hooks.HEADER_CHANNELS] == (
        f"{PUBLIC_CHANNEL}/linux-64;{PUBLIC_CHANNEL}/noarch"
    )
    assert headers[hooks.HEADER_PACKAGES] == ("defaults/linux-64::public-package-1.0-0")
    assert headers[hooks.HEADER_INSTALL] == "public-package"
    assert "private" not in " ".join(headers.values())


@pytest.mark.parametrize("command", ["search", "install"])
@pytest.mark.parametrize(
    "spec,expected",
    [
        ("conda-forge::public-package=1.0=0", "public-package"),
        ("private-organization::private-package", ""),
        ("https://private.example.test/private-package-1.0-0.conda", ""),
        ("/synthetic-private/private-package-1.0-0.tar.bz2", ""),
        (
            "private-package[url=https://private.example.test/private-package-1.0-0.conda]",
            "",
        ),
        (
            "conda-forge::private-package[url=https://private.example.test/private-package-1.0-0.conda]",
            "",
        ),
    ],
)
def test_request_specs_are_filtered_in_emitted_headers(
    mocker: MockerFixture, command: str, spec: str, expected: str
) -> None:
    mocker.patch.object(
        hooks.context,
        "_argparse_args",
        SimpleNamespace(cmd=command, packages=[spec], match_spec=spec),
    )
    if command == "install":
        capture_specs(spec)

    headers = emitted_headers()

    name = hooks.HEADER_SEARCH if command == "search" else hooks.HEADER_INSTALL
    assert headers[name] == expected
    assert "private" not in " ".join(headers.values())


@pytest.mark.parametrize("command", ["search", "install"])
def test_unqualified_names_are_omitted_with_private_configured_channels(
    mocker: MockerFixture, command: str
) -> None:
    set_channels(mocker, PUBLIC_CHANNEL, PRIVATE_CHANNEL)
    mocker.patch.object(
        hooks.context,
        "_argparse_args",
        SimpleNamespace(
            cmd=command, packages=["private-package"], match_spec="private-package"
        ),
    )
    if command == "install":
        capture_specs("private-package")

    headers = emitted_headers()

    name = hooks.HEADER_SEARCH if command == "search" else hooks.HEADER_INSTALL
    assert headers[name] == ""
    assert "private" not in " ".join(headers.values())


def test_private_multichannel_name_is_not_serialized(
    mocker: MockerFixture, header_context: MagicMock
) -> None:
    public_channel = Channel(PUBLIC_CHANNEL)
    mocker.patch(
        "conda.base.context.Context.custom_multichannels",
        new_callable=mocker.PropertyMock,
        return_value={"private-project": (public_channel,)},
    )
    set_channels(mocker, "private-project")
    record = package_record("public-package", PUBLIC_CHANNEL)
    assert record.channel.canonical_name == "private-project"
    header_context.return_value.iter_records.return_value = (record,)
    capture_specs("public-package")

    headers = emitted_headers()

    assert headers[hooks.HEADER_PACKAGES] == ("defaults/linux-64::public-package-1.0-0")
    assert headers[hooks.HEADER_INSTALL] == "public-package"
    assert "private-project" not in " ".join(headers.values())


@pytest.mark.parametrize("channels", [(), ("empty-channel",)])
def test_channels_without_public_urls_do_not_allow_package_names(
    mocker: MockerFixture, channels: tuple[str, ...]
) -> None:
    mocker.patch(
        "conda.base.context.Context.custom_multichannels",
        new_callable=mocker.PropertyMock,
        return_value={"empty-channel": ()},
    )
    set_channels(mocker, *channels)
    capture_specs("private-package")

    headers = emitted_headers()

    assert headers[hooks.HEADER_CHANNELS] == ""
    assert headers[hooks.HEADER_INSTALL] == ""


@pytest.mark.parametrize("channel_name", ["defaults", "conda-forge"])
def test_public_channel_name_redirected_to_private_url(
    mocker: MockerFixture, header_context: MagicMock, channel_name: str
) -> None:
    private_channel = Channel(PRIVATE_CHANNEL)
    if channel_name == "defaults":
        mocker.patch(
            "conda.base.context.Context.custom_multichannels",
            new_callable=mocker.PropertyMock,
            return_value={"defaults": (private_channel,)},
        )
    else:
        mocker.patch(
            "conda.base.context.Context.channel_alias",
            new_callable=mocker.PropertyMock,
            return_value=Channel(
                scheme="https", location="private.example.test", name=""
            ),
        )
    set_channels(mocker, channel_name)
    header_context.return_value.iter_records.return_value = (
        package_record("private-package", channel_name),
    )
    capture_specs(f"{channel_name}::private-package")

    headers = emitted_headers()

    assert headers[hooks.HEADER_CHANNELS] == ""
    assert headers[hooks.HEADER_PACKAGES] == ""
    assert headers[hooks.HEADER_INSTALL] == ""


def test_main_x_uses_actual_public_url(
    mocker: MockerFixture, header_context: MagicMock
) -> None:
    main_x = "https://repo.anaconda.cloud/repo/main-x"
    set_channels(mocker, main_x)
    header_context.return_value.iter_records.return_value = (
        package_record("public-package", main_x),
    )
    capture_specs(f"{main_x}::public-package")

    headers = emitted_headers()

    assert headers[hooks.HEADER_CHANNELS] == (f"{main_x}/linux-64;{main_x}/noarch")
    assert headers[hooks.HEADER_PACKAGES] == "main-x/linux-64::public-package-1.0-0"
    assert headers[hooks.HEADER_INSTALL] == "public-package"


def test_install_header_updates_after_pre_solve_and_resets_between_commands() -> None:
    capture_command("install")
    assert emitted_headers()[hooks.HEADER_INSTALL] == ""

    capture_requested_packages(frozenset({MatchSpec("first-package")}), frozenset())
    assert emitted_headers()[hooks.HEADER_INSTALL] == "first-package"

    clear_command()
    assert emitted_headers()[hooks.HEADER_INSTALL] == ""

    capture_specs("second-package")
    assert emitted_headers()[hooks.HEADER_INSTALL] == "second-package"

    capture_command("install")
    assert emitted_headers()[hooks.HEADER_INSTALL] == ""


def test_file_specs_with_unavailable_channel_configuration_are_omitted(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(
        hooks.context,
        "_argparse_args",
        SimpleNamespace(cmd="install", packages=[], file=["environment.yml"]),
    )
    capture_specs("private-package", "conda-forge::numpy")

    headers = emitted_headers()

    assert headers[hooks.HEADER_INSTALL] == "numpy"
    assert "private" not in " ".join(headers.values())
