from anaconda_conda_telemetry.hooks import conda_request_headers, HEADER_PREFIX


def test_conda_request_header_default_headers():
    """
    Ensure default headers are returned
    """
    headers = {header.name: header for header in tuple(conda_request_headers())}

    expected_header_names_values = {
        f"{HEADER_PREFIX}-Sys-Info": "",
        f"{HEADER_PREFIX}-Channels": "",
        f"{HEADER_PREFIX}-Virtual-Pkgs": "",
        f"{HEADER_PREFIX}-Packages": "",
    }
    expected_header_names = {key for key, _ in expected_header_names_values.items()}

    assert len(set(headers.keys()).intersection(expected_header_names)) == len(
        expected_header_names
    )


def test_conda_request_header_with_search(monkeypatch, mocker):
    """
    Ensure default headers are returned when conda search is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "search", "package"])
    mock_argparse_args = mocker.MagicMock(match_spec="package")
    mocker.patch(
        "anaconda_conda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers())}
    expected_header_names = {
        f"{HEADER_PREFIX}-Sys-Info",
        f"{HEADER_PREFIX}-Channels",
        f"{HEADER_PREFIX}-Virtual-Pkgs",
        f"{HEADER_PREFIX}-Packages",
        f"{HEADER_PREFIX}-Search",
    }

    assert len(header_names.intersection(expected_header_names)) == len(
        expected_header_names
    )


def test_conda_request_header_with_install(monkeypatch, mocker):
    """
    Ensure default headers are returned when conda search is invoked
    """
    monkeypatch.setattr("sys.argv", ["conda", "install", "package"])
    mock_argparse_args = mocker.MagicMock(packages=["package"])
    mocker.patch(
        "anaconda_conda_telemetry.hooks.context._argparse_args", mock_argparse_args
    )

    header_names = {header.name for header in tuple(conda_request_headers())}
    expected_header_names = {
        f"{HEADER_PREFIX}-Sys-Info",
        f"{HEADER_PREFIX}-Channels",
        f"{HEADER_PREFIX}-Virtual-Pkgs",
        f"{HEADER_PREFIX}-Packages",
        f"{HEADER_PREFIX}-Install",
    }

    assert len(header_names.intersection(expected_header_names)) == len(
        expected_header_names
    )
