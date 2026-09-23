# FAQ

## What happens when I enable conda-anaconda-telemetry?

When the `conda-anaconda-telemetry` plugin is installed in the conda base environment and enabled,
the plugin will collect additional information about how conda is being used. This is then submitted
to the channel servers that are currently configured via HTTP request headers and OpenTelemetry (OTel).
This allows channel owners to gain additional insights about how their channels are being used.

## What data is tracked by this plugin?

We currently collect the following information when this plugin is installed:

- Installed [virtual packages](https://docs.conda.io/projects/conda/en/stable/dev-guide/plugins/virtual_packages.html)
  (e.g., `glibc` version or your current architecture specifications, such as `m1`)
- Installed packages in the active environment (e.g. the output of `conda list`)
- Configured channels (e.g. `defaults` or `conda-forge`)
- System information (e.g. `conda-build` version or the command currently being run)
- When `conda search` is run, we track the packages that are being searched for
- When `conda install` or `conda create` is run, we track the packages that are being installed that are
  specified at the command line (e.g. for the command `conda install package-a package-b`, `package-a` and
  `package-b` will be tracked)
- Usage tokens provided by `anaconda-anon-usage` (e.g. a client token and a per-session token). For the exact fields that are exported - see [below](#ongoing-migration-to-use-otel).

## Which commands are you tracking?

We only track commands that make network requests. This includes the following:

- `conda search`
- `conda install`
- `conda update`
- `conda create`
- `conda remove`
- `conda notices`

## When are telemetry headers attached?

Telemetry headers (the `anaconda-telemetry-*` headers) are only added to HTTP
requests that match a small whitelist of hosts and paths. The plugin attaches
headers for requests to:

- `repo.anaconda.com` and `repo.anaconda.cloud` (any path), and
- `conda.anaconda.org/<channel>/...` for the channels: `anaconda`,
  `conda-forge`, `main`, `msys2`, and `r`.

Examples:

- Requests to `https://repo.anaconda.com/pkgs/main/...` will include telemetry headers.
- Requests to `https://conda.anaconda.org/conda-forge/...` will include telemetry headers.

This behavior is implemented in `conda_anaconda_telemetry/hooks.py` via a
compiled regular expression named `REQUEST_HEADER_PATTERN` which performs the
matching. Limiting submission to these hosts avoids adding telemetry headers to
unrelated third-party hosts.

## Telemetry data via OpenTelemetry
There is an existing parallel approach handling data which relies on OpenTelemetry (OTel). OpenTelemetry is an open-source framework designed to standardize how telemetry data is handled. The OTel-based approach is gated behind the same setting as the headers.

The OTel based approach will replace the header-based approach in the future.

Data handled via OTel are sent to Anaconda's servers, and only for the two conda commands `create` and `install`. Telemetry for these commands is only collected and exported when either command raises the `PackagesNotFoundInChannelsError` exception (events `create.pnfe` and `install.pnfe`) or when they succeed without any error (events `create.success` and `install.success`). The data that is being export contain information about:
- The installer used
- Conda version
- Operating system (type and version)
- The requested command (filtered to exclude private information)
- Requested packages
- Resolved packages (during success events)
- The Python version
- Whether the operation is running on CI
- Lastly, AAU tokens from the plugin `anaconda-anon-usage`

Among the AAU tokens the following are persistent:
- `aau.client.token`
- `aau.environment.token`
- `aau.organization.tokens`
- `aau.installer.tokens`
- `aau.machine.tokens`
- `aau.version`

The following are regenerated each run:
- `aau.session.token`

Lastly, the following are account-linked:
- `aau.anaconda_auth.token`
