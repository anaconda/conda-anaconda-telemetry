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
- Usage tokens provided by `anaconda-anon-usage` (e.g. a client token and a per-session token). For the exact fields that are exported - see [below](#telemetry-data-via-opentelemetry).

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

Data handled via OTel are sent to Anaconda's servers.

<!-- BEGIN GENERATED OTEL SIGNAL -->
### Signal version

The signal version is `1`. It is sent as `event.schema_version`, which the plugin sets. It is separate from `schema.version`, which the SDK sets.

### Events

- `install.pnfe`: Sent when `conda install` fails because a requested package is not in the configured channels. It is not sent when telemetry is disabled, when the plugin has no record of the request, or when a package name cannot be read (for example, a URL spec).
- `create.pnfe`: Sent when `conda create` fails because a requested package is not in the configured channels. It is not sent when telemetry is disabled, when the plugin has no record of the request, or when a package name cannot be read (for example, a URL spec).
- `install.success`: Sent when `conda install` succeeds. It is not sent when telemetry is disabled, for dry runs, for download-only runs, or when the plugin has no record of the request or the result.
- `create.success`: Sent when `conda create` succeeds. It is not sent when telemetry is disabled, for dry runs, for download-only runs, or when the plugin has no record of the request or the result.

### Resource attributes

| Name | Description | Owner | Presence |
| --- | --- | --- | --- |
| `aau.anaconda_auth.token` | Identifier of the Anaconda account, taken from the sign-in of anaconda-auth. It is not the API key. | sdk | optional: The user is signed in through anaconda-auth. |
| `aau.client.token` | Token that identifies this client installation. It persists between runs. | sdk | optional: The `anaconda-anon-usage` package is installed and can read or create its client token file. |
| `aau.environment.token` | Token that identifies the conda environment. It persists between runs. | sdk | optional: The `anaconda-anon-usage` package is installed and can read or create the token file of the environment. |
| `aau.installer.tokens` | Tokens that identify the installer used to install conda. They persist between runs. | sdk | optional: The `anaconda-anon-usage` package is installed and a valid installer token is configured, in a token file or in an environment variable. |
| `aau.machine.tokens` | Tokens that identify the machine. They persist between runs. | sdk | optional: The `anaconda-anon-usage` package is installed and a valid machine token is configured, in a token file or in an environment variable. |
| `aau.organization.tokens` | Tokens that identify the organization. They persist between runs. | sdk | optional: The `anaconda-anon-usage` package is installed and a valid organization token is configured, in a token file or in an environment variable. |
| `aau.session.token` | Token for the current run. It changes with each run. | sdk | optional: The `anaconda-anon-usage` package is installed. |
| `aau.version` | Version of the `anaconda-anon-usage` package. | sdk | optional: The `anaconda-anon-usage` package is installed. |
| `client.sdk.version` | Version of the Anaconda OpenTelemetry SDK that sends the signal. | sdk | always |
| `conda.ci_detected` | Whether the `CI` environment variable is set to a true value (`true` or `false`). | plugin | always |
| `conda.version` | Version of conda that sends the signal. | plugin | always |
| `environment` | Label of the deployment. It comes from the `ATEL_ENVIRONMENT` setting and is `production` by default. | plugin | always |
| `installer.name` | Name of the installer that installed conda. | plugin | optional: The installer metadata file (.installer.info) in the base environment exists and is valid. |
| `installer.platform` | Platform of the installer that installed conda. | plugin | optional: The installer metadata file (.installer.info) in the base environment exists and is valid. |
| `installer.version` | Version of the installer that installed conda. | plugin | optional: The installer metadata file (.installer.info) in the base environment exists and is valid. |
| `os.type` | Type of the operating system. | sdk | always |
| `os.version` | Version of the operating system. | sdk | always |
| `parameters` | Extra attributes that the SDK groups into one attribute. | sdk | always |
| `platform` | Name of the product platform that sends the signal (conda). | plugin | always |
| `python.version` | Version of Python that runs conda. | sdk | always |
| `schema.version` | Version of the SDK telemetry schema. It is not the same as `event.schema_version`. | sdk | always |
| `service.instance.id` | ID of this instance of the sending service. The OpenTelemetry SDK sets it. | sdk | always |
| `service.name` | Name of the sending service (conda-anaconda-telemetry). | plugin | always |
| `service.version` | Version of the conda-anaconda-telemetry plugin. | plugin | always |
| `telemetry.sdk.language` | Programming language of the OpenTelemetry SDK. | sdk | always |
| `telemetry.sdk.name` | Name of the OpenTelemetry SDK. | sdk | always |
| `telemetry.sdk.version` | Version of the OpenTelemetry SDK. | sdk | always |

### Anaconda token classes

- `persistent`: Persistent tokens stay the same between runs. Attributes: `aau.client.token`, `aau.environment.token`, `aau.installer.tokens`, `aau.machine.tokens`, `aau.organization.tokens`.
- `per-run`: Per-run tokens change with each run. Attributes: `aau.session.token`.
- `account-linked`: Account-linked tokens are tied to an Anaconda account. Attributes: `aau.anaconda_auth.token`.

### Log attributes: `pnfe` outcome

Events: `install.pnfe`, `create.pnfe`.

| Name | Description | Owner | Presence |
| --- | --- | --- | --- |
| `command` | The conda command that ran. | plugin | always |
| `event.schema_version` | Version of this signal format. It is not the same as `schema.version`. | plugin | always |
| `exception.missing_specs` | Names of the packages that were not found. Only package names are sent, with no versions or URLs. | plugin | always |
| `exception.name` | Name of the error that conda raised. | plugin | always |
| `install.channel_priority` | The channel priority setting of conda. | plugin | always |
| `install.channels` | Channels used for the request. Only `defaults`, `main`, `main-x` and `conda-forge` are sent by name. Any other channel is sent as `other`. | plugin | always |
| `log.event.name` | Name of the event. | sdk | always |
| `requested.packages` | Names of the packages that the user requested. Only package names are sent, with no versions or URLs. | plugin | always |
| `truncated` | Whether the plugin shortened a list to keep the signal small. | plugin | always |

### Log attributes: `success` outcome

Events: `install.success`, `create.success`.

| Name | Description | Owner | Presence |
| --- | --- | --- | --- |
| `command` | The conda command that ran. | plugin | always |
| `event.schema_version` | Version of this signal format. It is not the same as `schema.version`. | plugin | always |
| `install.channel_priority` | The channel priority setting of conda. | plugin | always |
| `install.channels` | Channels used for the request. Only `defaults`, `main`, `main-x` and `conda-forge` are sent by name. Any other channel is sent as `other`. | plugin | always |
| `log.event.name` | Name of the event. | sdk | always |
| `requested.packages` | Names of the packages that the user requested. Only package names are sent, with no versions or URLs. | plugin | always |
| `resolved.packages` | Packages that the solver chose to install. | plugin | always |
| `truncated` | Whether the plugin shortened a list to keep the signal small. | plugin | always |
<!-- END GENERATED OTEL SIGNAL -->
