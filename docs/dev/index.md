# Developer Guide

This developer guide is split into two parts: setting up your development
environment and a discussion on how the plugin itself functions.

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
a character limit, with `Anaconda-Telemetry-Packages` getting the highest limit because it is
inherently larger than the other headers. When a header's data is larger than its limit, the data is
truncated and submitted as partial data.

Below is a table showing the current headers, along with their size limits:

| Header                                | Size (in bytes) |
|---------------------------------------|-----------------|
| `Anaconda-Telemetry-Virtual-Packages` | 500             |
| `Anaconda-Telemetry-Channels`         | 500             |
| `Anaconda-Telemetry-Packages`         | 5,000           |
| `Anaconda-Telemetry-Channels`         | 500             |
| `Anaconda-Telemetry-Search`           | 500             |
| `Anaconda-Telemetry-Install`          | 500             |
| `Anaconda-Telemetry-Sys-Info`         | 500             |


```{toctree}
:hidden:

manual_testing
```


[conda-plugins-request-headers]: https://docs.conda.io/projects/conda/en/stable/dev-guide/plugins/request_headers.html
