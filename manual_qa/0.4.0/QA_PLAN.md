# QA Testing Plan - conda-anaconda-telemetry 0.4.0 (OpenTelemetry events)

**Submitted by**: Robin Andersson

**Date**: [16/09/2026]

## 1. Feature/Package Overview

**Name**: conda-anaconda-telemetry - OpenTelemetry (OTel) event signals for `conda install` and `conda create`

**Version**: 0.4.0

**Brief Description**:

`conda-anaconda-telemetry` is a conda plugin that sends usage data to Anaconda. This release adds a new, separate way of sending that data (using a standard called OpenTelemetry). It sends one report (signal) each time `conda install` or `conda create` succeeds, or fails because a package wasn't found (an error called `PackagesNotFoundInChannelsError`, or "PNFE" for short).

## 2. System Requirements

### Operating System

* [x] Windows 11 (64-bit)
* [x] macOS (latest, arm64)
* [x] Linux Ubuntu (latest LTS, x86_64)
* [ ] Other

### Dependencies

* Required Packages/Libraries:

```
python >=3.10
conda >=26.7.2
anaconda-opentelemetry >=1.2.2
conda-anaconda-telemetry 0.4.0 (installed in the base environment)
```

* Other Requirements: Internet access; approximately 2 GB of free disk space for temporary environments; `Docker` for the local collector test in S15.

## 3. Installation Steps

### Prerequisites

Install a fresh Miniconda in `~/conda-qa` (`%USERPROFILE%\conda-qa` on Windows) to prevent host conda configuration from affecting results. Install the plugin in the base environment because that is where conda runs.

### Installation Commands

#### Linux (x86_64)

```shell
# Step 1: Download Miniconda.
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh

# Step 2: Install without automatic activation.
bash /tmp/miniconda.sh -b -p ~/conda-qa

# Step 3: Initialize conda, then restart the shell.
~/conda-qa/bin/conda init

# Step 4: Install conda and the plugin in base.
conda install -n base -c defaults "conda=26.7.2" "conda-anaconda-telemetry=0.4.0"
```

#### Windows (64-bit, PowerShell)

```powershell
# Step 1: Download Miniconda.
curl.exe -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o "$env:TEMP\miniconda.exe"

# Step 2: Install silently.
Start-Process -Wait "$env:TEMP\miniconda.exe" -ArgumentList "/S /D=$env:USERPROFILE\conda-qa"

# Step 3: Open Anaconda PowerShell Prompt and install conda and the plugin in base.
conda install -n base -c defaults "conda=26.7.2" "conda-anaconda-telemetry=0.4.0"
```

### Verification

```shell
# Confirm that the active installation is the QA installation.
conda info

# Confirm package versions.
conda --version                                      # expected: 26.7.2
conda list -n base conda-anaconda-telemetry          # expected: 0.4.0
conda list -n base anaconda-opentelemetry            # expected: 1.2.2 or newer

# Confirm that the plugin is registered and enabled.
conda config --describe plugins.anaconda_telemetry   # expected: default value True
```

## 4. Configuration

### Environment Variables

| Variable | Purpose |
| --- | --- |
| `ATEL_ENVIRONMENT` | Selects `production` (default), `staging`, `development`, or `test`. `development` and `test` use `http://localhost:4318`. |
| `ATEL_DEFAULT_ENDPOINT` | Overrides the collector endpoint. Accepted values use `https://` or `grpc://`, or `http://` with `localhost` or `127.0.0.1`. |
| `CONDA_PLUGINS_ANACONDA_TELEMETRY` | Overrides the conda setting; `false` disables the plugin for one command. |

Use Mode A for S1-S14 and S16. Use Mode B only for S15.

**Mode A - console exporter (no container):** A `localhost` endpoint makes the SDK print the signal to stdout without sending it over the network.

```shell
export ATEL_ENVIRONMENT=development
# PowerShell: $env:ATEL_ENVIRONMENT = "development"
```

**Mode B - local OpenTelemetry collector (Docker):** Create `otel-collector.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
exporters:
  debug:
    verbosity: detailed
service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [debug]
```
Ensure that `docker` is running before you run any `docker` command below. Note that we use 2 separate terminals to do this.
```shell
# Terminal 1 (Linux/macOS): run the collector and watch its output.
docker run --rm -p 4318:4318 \
  -v "$PWD/otel-collector.yaml:/etc/otelcol/config.yaml" \
  otel/opentelemetry-collector:latest

# Terminal 2: configure the plugin.
export ATEL_DEFAULT_ENDPOINT=http://127.0.0.1:4318
export ATEL_ENVIRONMENT=development
```

```powershell
# Terminal 1 (Windows PowerShell): run the collector and watch its output.
docker run --rm -p 4318:4318 `
  -v "${PWD}\otel-collector.yaml:/etc/otelcol/config.yaml" `
  otel/opentelemetry-collector:latest

# Terminal 2: configure the plugin.
$env:ATEL_DEFAULT_ENDPOINT = "http://127.0.0.1:4318"
$env:ATEL_ENVIRONMENT = "development"
```

### Setup Instructions

1. Complete section 3, including verification.
2. Configure Mode A and keep it active unless a scenario says otherwise.
3. Run scenarios from base and store each signal (outputted as JSON) as evidence.

## 5. Impacted Areas

### Files Modified/Added

```
conda_anaconda_telemetry/otel.py                  # SDK configuration, event attributes, sanitization
conda_anaconda_telemetry/plugin.py                # Command state and success/PNFE reporting
conda_anaconda_telemetry/resource_attributes.py   # conda.* and installer.* resource attributes
conda_anaconda_telemetry/hooks.py                 # conda hook registration
recipe/meta.yaml, pyproject.toml                  # anaconda-opentelemetry >=1.2.2 dependency
```

### Modules/Components Affected

* **When telemetry runs** - The plugin now watches `create` and `install` commands at several points (before/after they run, and if they fail) to send telemetry. No other conda commands are watched.
* **What gets sent** - A new type of report is added on top of the existing one that was already being sent. Think of it as a second, separate delivery of usage data.
* **What doesn't change** - conda still behaves exactly the same way (same messages, same exit codes) whether or not this new reporting works.

## 6. Testing Scope

### Expected Behavior

Each command should send exactly one report: a "success" report if it works, or a "not found" report if it fails because a package doesn't exist. If sending the report itself fails, that must NOT cause any visible error, crash, or change to conda's normal behavior.

For every scenario below, unless stated otherwise, check that:
- **Exactly one** report was sent.
- conda behaved normally (same messages, same exit code, no crash/error).
- The report includes all the expected fields (see table below).
- The report does NOT contain any sensitive info: no website addresses, private server names, passwords/tokens, file paths, environment names, or usernames.

Save a copy of the report (as shown in your console, or in the collector tool) as proof for each test.

A "success" report includes what packages were requested and what was actually installed. A "not found" report includes what was requested and the name of the error, but does NOT include what was installed (since nothing was installed).

| Attribute | Expected value |
| --- | --- |
| `log.event.name` | `install.success`, `create.success`, `install.pnfe`, or `create.pnfe` |
| `command` | `install` or `create` |
| `event.schema_version` | `1` |
| `install.channels` | Only these four channel names are shown as-is: `defaults`, `main`, `main-x`, `conda-forge`. Any other channel name is replaced with the generic word `other` (so it can't leak private channel names). |
| `install.channel_priority` | `flexible`, `strict`, or `disabled` |
| `requested.packages` | Sorted, deduplicated package names from the command line and solve |
| `resolved.packages` | Success only: `name=version=build` for each linked package |
| `exception.name` | PNFE only: `PackagesNotFoundInChannelsError` |
| `exception.missing_specs` | PNFE only: missing package names |
| `truncated` | `true` if the list of packages was too long and got cut off (max 50 items, or 500 bytes of data, whichever comes first) |

The report also includes some general info about the system: the plugin's own name/version, whether it's running in CI, the OS type/version, the Python version, a random session ID, an anonymized (hashed) hostname, and some internal tracking tokens (`aau.*`). If the installer was made with a recent enough tool (constructor 3.16.0+), it also includes the installer's name, version, and platform.

### Test Scenarios to Cover

#### S1 - `create.success`

```shell
conda create -y -n qa-s1 -c defaults python=3.12
```

Once the command above finishes you should see the signal being sent to your terminal. Verify one `create.success` event with (see the nested `attributes` field) `command` `create`, `install.channels` `['defaults']`, `install.channel_priority` `flexible`, `requested.packages` `['python']`, and `resolved.packages` containing Python and all linked dependencies. Verify all applicable resource attributes.

#### S2 - `install.success`

```shell
conda install -y -n qa-s1 -c defaults numpy
```

Using the environment created in S1, verify one `install.success` event with `command` `install`, `requested.packages` `['numpy']`, and `resolved.packages` containing `numpy=<version>=<build>` and any newly linked dependencies.

#### S3 - `install.pnfe`

```shell
conda install -y -n qa-s1 -c defaults definitely-not-a-real-package-xyz
```

Verify normal `PackagesNotFoundError`/`PackagesNotFoundInChannelsError` failure and one `install.pnfe` event with `exception.name` `PackagesNotFoundInChannelsError`, `exception.missing_specs` `['definitely-not-a-real-package-xyz']`, and the same value in `requested.packages`. Verify `resolved.packages` is absent.

#### S4 - `create.pnfe` with `--dry-run`

```shell
conda create -n qa-s4 --dry-run -c defaults definitely-not-a-real-package-xyz
```

Verify the S3 PNFE shape with `log.event.name` `create.pnfe` and `command` `create`. The event must be emitted despite `--dry-run` because the solve fails.

#### S5 - Opt-out

```shell
conda config --set plugins.anaconda_telemetry false
conda create -y -n qa-s5 -c defaults zlib
conda create -n qa-s5b --dry-run -c defaults definitely-not-a-real-package-xyz
conda config --set plugins.anaconda_telemetry true
conda create -n qa-s5c --dry-run -c defaults definitely-not-a-real-package-xyz
```

Verify that the `qa-s5` success command and the `qa-s5b` PNFE command emit no events while `plugins.anaconda_telemetry` is `false`. After resetting the setting to `true`, verify the `qa-s5c` command emits one `create.pnfe` event.

Verify the environment-variable override disables telemetry for one command without changing the saved configuration:

```shell
# Linux and macOS
CONDA_PLUGINS_ANACONDA_TELEMETRY=false conda create -n qa-s5d --dry-run -c defaults definitely-not-a-real-package-xyz
```

```powershell
# Windows PowerShell
$env:CONDA_PLUGINS_ANACONDA_TELEMETRY = "false"
conda create -n qa-s5d --dry-run -c defaults definitely-not-a-real-package-xyz
Remove-Item Env:CONDA_PLUGINS_ANACONDA_TELEMETRY
```

Verify the `qa-s5d` command emits no event. Then rerun it without the environment-variable override and verify one `create.pnfe` event, confirming the saved `true` configuration remains active.

#### S6 - Channel allow-list and privacy

```shell
conda create -n qa-s6 --dry-run -c bioconda -c conda-forge -c defaults definitely-not-a-real-package-xyz
```

Check that `install.channels` shows `['other', 'conda-forge', 'defaults']` - since `bioconda` isn't on the approved list, it's replaced with `other` (but the order stays the same).

Next, do the same test using a local folder pretending to be a channel instead of a real one online. The steps below create some empty test files so conda thinks this folder is a valid channel.

```shell
# Linux and macOS
mkdir -p /tmp/local-channel/noarch /tmp/local-channel/linux-64 /tmp/local-channel/osx-arm64
printf '{"packages":{},"packages.conda":{}}\n' > /tmp/local-channel/noarch/repodata.json
printf '{"packages":{},"packages.conda":{}}\n' > /tmp/local-channel/linux-64/repodata.json
printf '{"packages":{},"packages.conda":{}}\n' > /tmp/local-channel/osx-arm64/repodata.json
conda create -n qa-s6-file --dry-run -c file:///tmp/local-channel -c conda-forge -c defaults definitely-not-a-real-package-xyz
```

```powershell
# Windows PowerShell
$channel = Join-Path $env:TEMP "qa-local-channel"
New-Item -ItemType Directory -Force (Join-Path $channel "noarch"), (Join-Path $channel "win-64") | Out-Null
$emptyRepodata = '{"packages":{},"packages.conda":{}}'
[System.IO.File]::WriteAllText((Join-Path $channel "noarch\repodata.json"), $emptyRepodata)
[System.IO.File]::WriteAllText((Join-Path $channel "win-64\repodata.json"), $emptyRepodata)
$channelUri = ([System.Uri]::new("$channel\")).AbsoluteUri.TrimEnd('/')
conda create -n qa-s6-file --dry-run -c $channelUri -c conda-forge -c defaults definitely-not-a-real-package-xyz
```

Confirm the local folder is also reported as `other`, and that no folder path, web address, or private info shows up anywhere in the report. Also confirm the command emits `create.pnfe`.

#### S7 - Package-spec handling

```shell
# Linux x86_64
conda install -y -n qa-s1 -c defaults \
  "https://repo.anaconda.com/pkgs/main/linux-64/zlib-1.3.2-h47b2149_0.conda"
```

```shell
# macOS (arm64)
conda install -y -n qa-s1 -c defaults \
  "https://repo.anaconda.com/pkgs/main/osx-arm64/zlib-1.3.2-hb4cf58c_0.conda"
```

```powershell
# Windows PowerShell
conda install -y -n qa-s1 -c defaults "https://repo.anaconda.com/pkgs/main/win-64/zlib-1.3.2-h1c6eee0_0.conda"
```

Verify the install succeeds but emits no event. Next, download the same package and install it from a local `file://` URI. Use `--force-reinstall` because the package was installed by the preceding command.

```shell
# Linux x86_64
curl -L "https://repo.anaconda.com/pkgs/main/linux-64/zlib-1.3.2-h47b2149_0.conda" \
  -o /tmp/zlib-1.3.2-h47b2149_0.conda
conda install -y --force-reinstall -n qa-s1 \
  "file:///tmp/zlib-1.3.2-h47b2149_0.conda"
```

```shell
# macOS (arm64)
curl -L "https://repo.anaconda.com/pkgs/main/osx-arm64/zlib-1.3.2-hb4cf58c_0.conda" \
  -o /tmp/zlib-1.3.2-hb4cf58c_0.conda
conda install -y --force-reinstall -n qa-s1 \
  "file:///tmp/zlib-1.3.2-hb4cf58c_0.conda"
```

```powershell
# Windows PowerShell
$packagePath = Join-Path $env:TEMP "zlib-1.3.2-h1c6eee0_0.conda"
Invoke-WebRequest "https://repo.anaconda.com/pkgs/main/win-64/zlib-1.3.2-h1c6eee0_0.conda" -OutFile $packagePath
$packageUri = ([System.Uri]::new((Resolve-Path $packagePath).Path)).AbsoluteUri
conda install -y --force-reinstall -n qa-s1 $packageUri
```

Verify the local-file installation completes and emits no event (this confirm that package URLs are not reported as requested package names). Then run `conda install -y -n qa-s1 -c defaults defaults::xz`; verify an event is emitted and `requested.packages` contains bare name `xz`.

#### S8 - No success event without installation

```shell
conda install -y -n qa-s1 -c defaults --dry-run xz
conda install -y -n qa-s1 -c defaults --download-only xz
```

Verify both commands complete **without** an `install.success` event.

#### S9 - List truncation

```shell
# Linux and macOS
packages=()
for number in {000..059}; do packages+=("xq$number"); done
conda create -n qa-s9-pnfe --dry-run -c defaults "${packages[@]}"
conda create -y -n qa-s9 -c defaults jupyter
```

```powershell
# Windows PowerShell
$packages = 0..59 | ForEach-Object { "xq{0:D3}" -f $_ }
conda create -n qa-s9-pnfe --dry-run -c defaults @packages
conda create -y -n qa-s9 -c defaults jupyter
```

* Verify the `qa-s9-pnfe` event has `truncated` `true` and exactly 50 complete entries in `requested.packages`, from `xq000` through `xq049`. Here, `conda` may report only `xq000` in `exception.missing_specs`; this is expected and does not affect this check.
* Verify the `qa-s9` `create.success` event has `requested.packages` `['jupyter']` and `truncated` `true`. Its resolved list will likely contain much fewer than 50 entries because the approximately 500-byte limit is reached first.

These two commands test the two different ways a list can get cut short: hitting the max item count (50), and hitting the max data size (500 bytes).

#### S10 - Nothing left to install

```shell
conda install -y -n qa-s1 -c defaults numpy
```

With `numpy` already installed by S2, verify one `install.success` event with `requested.packages` `['numpy']` and an empty `resolved.packages` list.

#### S11 - Other commands

Create a minimal `environment.yml` before the final command:

```yaml
name: qa-s11-file
dependencies:
  - zlib
```

```shell
conda remove -y -n qa-s1 numpy
conda update -y -n qa-s1 --all
conda search -c defaults zlib
conda list -n qa-s1
conda env create -n qa-s11 -f environment.yml
```

Verify `remove`, `update`, `search`, and `list` emit no OTel event. With `conda 26.7.2` or newer, verify `conda env create` emits one `create.success` event with `command` `create`, `requested.packages` `['zlib']`, and `resolved.packages` containing the packages installed into the new environment.

#### S12 - Collector unreachable or offline

```shell
# Linux and macOS
ATEL_DEFAULT_ENDPOINT=http://127.0.0.1:4999 conda create -n qa-s12 --dry-run -c defaults definitely-not-a-real-package-xyz
```

```powershell
# Windows PowerShell
$env:ATEL_DEFAULT_ENDPOINT = "http://127.0.0.1:4999"
conda create -n qa-s12 --dry-run -c defaults definitely-not-a-real-package-xyz
Remove-Item Env:ATEL_DEFAULT_ENDPOINT
```

With no service on port 4999, verify normal PNFE output and exit code, no traceback or noticeable delay compared with telemetry disabled, and no hang. One `Anaconda OpenTelemetry: No access to the endpoint...` line on stderr is expected.

Then repeat with an address that silently drops packets instead of refusing the connection, to confirm the plugin also handles a timeout rather than an immediate refusal:

```shell
# Linux and macOS
ATEL_DEFAULT_ENDPOINT=https://192.0.2.1:4999 conda create -n qa-s12b --dry-run -c defaults definitely-not-a-real-package-xyz
```

```powershell
# Windows PowerShell
$env:ATEL_DEFAULT_ENDPOINT = "https://192.0.2.1:4999"
conda create -n qa-s12b --dry-run -c defaults definitely-not-a-real-package-xyz
Remove-Item Env:ATEL_DEFAULT_ENDPOINT
```

Verify the same normal PNFE output and exit code, and that conda finishes within a few seconds rather than hanging (see Performance Considerations).

#### S13 - Invalid telemetry configuration

```shell
# Linux and macOS
ATEL_ENVIRONMENT=bogus conda create -n qa-s13 --dry-run -c defaults definitely-not-a-real-package-xyz
ATEL_DEFAULT_ENDPOINT=http://example.com:4318 conda create -n qa-s13 --dry-run -c defaults definitely-not-a-real-package-xyz
ATEL_DEFAULT_ENDPOINT=not-a-url conda create -y -n qa-s13 -c defaults zlib
```

```powershell
# Windows PowerShell
$env:ATEL_ENVIRONMENT = "bogus"
conda create -n qa-s13 --dry-run -c defaults definitely-not-a-real-package-xyz
$env:ATEL_ENVIRONMENT = "development"  # restore Mode A

$env:ATEL_DEFAULT_ENDPOINT = "http://example.com:4318"
conda create -n qa-s13 --dry-run -c defaults definitely-not-a-real-package-xyz
Remove-Item Env:ATEL_DEFAULT_ENDPOINT

$env:ATEL_DEFAULT_ENDPOINT = "not-a-url"
conda create -y -n qa-s13 -c defaults zlib
Remove-Item Env:ATEL_DEFAULT_ENDPOINT
```

Verify each command has the same output and exit code as telemetry-disabled execution, emits no event, and prints no traceback. The plugin must reject plain HTTP except for `localhost` and `127.0.0.1`, and reject malformed URLs.

#### S14 - Installer attributes

Inspect `~/conda-qa/.installer.info` (`%USERPROFILE%\conda-qa\.installer.info` on Windows). If present, verify `installer.name`, `installer.version`, and `installer.platform` match its corresponding fields and `type` is absent.

Back up the file, then overwrite it with this incomplete, invalid JSON:

```json
{
```
Full backup and replace code block below:
```shell
# Linux and macOS
cp ~/conda-qa/.installer.info ~/conda-qa/.installer.info.qa-backup
printf '{\n' > ~/conda-qa/.installer.info
conda create -y -n qa-s14 -c defaults zlib
mv ~/conda-qa/.installer.info.qa-backup ~/conda-qa/.installer.info
```

```powershell
# Windows PowerShell
$installerInfo = "$env:USERPROFILE\conda-qa\.installer.info"
Copy-Item $installerInfo "$installerInfo.qa-backup"
Set-Content -Path $installerInfo -Value '{'
conda create -y -n qa-s14 -c defaults zlib
Move-Item -Force "$installerInfo.qa-backup" $installerInfo
```

Verify the invalid JSON does not prevent the event and simply omits all three `installer.*` attributes. If the file is absent, record that the installer may predate constructor 3.16.0.

#### S15 - Local collector export (Mode B)

Switch to Mode B and repeat S1-S4. For each command, check the collector's output (Terminal 1) instead of the terminal where you ran the `conda` command: verify it shows exactly one decoded log record with the same attributes as Mode A. This confirms events are actually sent over the network to a collector, not just printed locally.

#### S16 - Cross-platform matrix

Repeat S1-S5 and S12 on Windows 11, macOS arm64, and Linux x86_64. Verify `os.type`, `os.version`, and `python.version` match.

### User Roles/Permissions to Test

* [ ] Regular user: run all scenarios using the user-writable `~/conda-qa` installation.
* [ ] Administrator/root: run S1-S4 using a fresh system-wide installation such as `/opt/conda-qa`; follow the same platform installation commands with an elevated shell and the system-wide prefix. Verify `.installer.info` can be read and telemetry works without a writable `$HOME`.

## 7. Known Issues & Limitations

* The signal still contains `hostname` and `session.id` in resource attributes pending [#236](https://github.com/anaconda/conda-anaconda-telemetry/issues/236); SDK 1.2.2 hashes `hostname`. This is expected, not a privacy bug.
* Only `PackagesNotFoundInChannelsError` is reported; `UnsatisfiableError`, network errors, `CondaValueError`, and other failures intentionally emit nothing. No event in these cases is expected, not a bug.
* Existing HTTP-header telemetry remains active alongside OTel telemetry in 0.4.0; don't mistake this legacy traffic for the new OTel events when inspecting network activity.
* `install.channels`/`create.channels` omit channels supplied only via an environment file (`--file`) passed to `conda install`/`create`; only channels configured via `.condarc`/CLI at command-start time are captured. Tracked in [#237](https://github.com/anaconda/conda-anaconda-telemetry/issues/237).

## 8. Additional Information

### Performance Considerations

Telemetry only adds delay on commands that emit an event (success or PNFE). When the collector is reachable, expect an extra few hundred milliseconds. When it's unreachable, conda should still finish within a few seconds, not hang. Report anything that feels like a hang.

### Security Considerations

No channel URL, private-channel host, token, file path, environment name, or username may appear in any payload. Channels are allow-listed and other names become `other`; an invalid package name suppresses the event. Inspect every captured payload for these values.

Repeat the S2 test, but first set a special variable named `OTEL_RESOURCE_ATTRIBUTES` to the value `foo.bar=leak`. Confirm that `foo.bar` does NOT show up in the report (i.e., the plugin ignores this attempt to inject extra data), and that the variable's value is unchanged afterward. Then repeat once more setting `CI=true`, and confirm the report's `conda.ci_detected` field shows `true`.

Production sends events to `https://public.telemetry.anaconda.com/v1/logs`. Keep Mode A or Mode B configured throughout QA to prevent test data from reaching production.

## 9. References & Resources

### Documentation

* Plugin: https://github.com/anaconda/conda-anaconda-telemetry
* Plugin documentation: https://anaconda.github.io/conda-anaconda-telemetry/
* Telemetry SDK and payload schema: https://github.com/anaconda/anaconda-otel-python (`docs/source/getting_started.md` and `docs/source/schema-versions.md`)
* OpenTelemetry collector image: https://hub.docker.com/r/otel/opentelemetry-collector

### Related Tickets/Issues

* [Suppress hostname and session ID #236](https://github.com/anaconda/conda-anaconda-telemetry/issues/236)

### Demo/Prototype

* `tests/test_otlp_integration.py` is an integration test with the exact signal verification; using a local HTTP server.

### Edge Cases & Test Ideas

Run these additional checks:

* Run two conda commands consecutively and verify distinct `session.id` values and no state leakage, such as a failed install followed by a successful create.
* Interrupt an install with Ctrl+C and verify no event or traceback.

## 10. Timeline

**Ready for Testing Date**: [DD/MM/YYYY]

**Target Completion Date**: [DD/MM/YYYY]

**Deployment Date**: [DD/MM/YYYY]

## Notes for Testing Team

Install the plugin in base. Use Mode A for payload checks and Mode B only for S15; use `127.0.0.1` in Mode B because `localhost` selects the console exporter. Attach raw JSON or collector output for each scenario.

### Final Cleanup

Once all scenarios are complete, uninstall the QA installation using the Miniconda uninstaller, which removes every environment created during testing along with the installation itself:

```shell
# Linux and macOS
conda deactivate
~/conda-qa/uninstall.sh
```

```powershell
# Windows PowerShell
Start-Process -FilePath "$env:USERPROFILE\conda-qa\Uninstall-Miniconda3.exe" -ArgumentList "/S" -Wait
```
