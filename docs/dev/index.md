# Developer Guide

This guide covers development setup, the plugin's technical design, and
maintainer information.

## Development environment

```{note}
The development environment setup is currently only available for users
of unix-like operating systems (e.g. macOS or Linux)
```

To set up your development environment, first clone the repository:

```
git clone git@github.com:anaconda/conda-anaconda-telemetry.git
```

From the root of the project directory, run the `develop.sh` script by sourcing it:

```
source develop.sh
```

This script performs the following:

- Creates a new conda environment while installing needed dependencies
- Activates this environment
- Installs an editable version of the plugin
- Modifies `CONDA_EXE` to point at the locally installed conda

After it finishes running, you will have a development environment setup that you
can start using.

## Technical design

The Conda Anaconda Telemetry plugin functions by attaching additional telemetry data
to HTTP request headers submitted to Anaconda channel servers. This is done by relying
on the [conda plugin for request headers][conda-plugins-request-headers].

The entire plugin consists of just a single `hooks.py` module and currently submits up to
five headers per request. To respect size limits (typically 8KB), each header has been given
a character limit, with `anaconda-telemetry-packages` getting the highest limit because it is
inherently larger than the other headers. When a header's data is larger than its limit, the data is
truncated and submitted as partial data.

Below is a table showing the current headers, along with their size limits:

| Header                                | Size (in bytes) |
|---------------------------------------|-----------------|
| `anaconda-telemetry-virtual-packages` | 500             |
| `anaconda-telemetry-channels`         | 500             |
| `anaconda-telemetry-packages`         | 5,000           |
| `anaconda-telemetry-search`           | 500             |
| `anaconda-telemetry-install`          | 500             |
| `anaconda-telemetry-sys-info`         | 500             |

In addition to request headers, the plugin reports discrete events over OpenTelemetry
(OTLP) logs using the `anaconda-opentelemetry` package. This is done by the
`AnacondaTelemetry` class in `otel.py`, which is used by `plugin.py` to report on the
`install` and `create` commands.

Similar to the headers, data sent over OTLP can also be truncated.
List-valued attributes on these events, such as `requested.packages`, `resolved.packages`,
and `install.channels`, are limited to 50 items and 500 bytes once serialized. When an
attribute's data is larger than its limit, the data is truncated and the event's
`truncated` attribute is set to `true`.

Below is a table showing the currently reported events, along with what triggers them:

| Event                | Trigger                                                |
|-----------------------|---------------------------------------------------------|
| `<command>.pnfe`      | `PackagesNotFoundInChannelsError` is raised            |
| `<command>.success`   | The command completes and packages were linked        |

Unlike the header mechanism, events are sent to a single pinned production endpoint
(`https://public.telemetry.anaconda.com/v1/logs`) rather than attached to existing
conda requests. Other endpoint overrides are ignored unless they point at a local
loopback HTTP collector, for local testing only.

## Maintainer information

Conda Anaconda Telemetry (`conda-anaconda-telemetry`) uses increasing
`MAJOR.MINOR.PATCH` version numbers for final releases, such as `0.3.1`, following
[PEP 440](https://packaging.python.org/en/latest/specifications/version-specifiers/#version-scheme).
Release tags contain the version number without a `v` prefix. The package version
is derived from Git tags by `hatch-vcs`, as configured in `pyproject.toml`.

For vulnerability reporting and the coordinated disclosure policy, see
[Anaconda's security.txt](https://www.anaconda.com/.well-known/security.txt).


```{toctree}
:hidden:

manual_testing
```


[conda-plugins-request-headers]: https://docs.conda.io/projects/conda/en/stable/dev-guide/plugins/request_headers.html
