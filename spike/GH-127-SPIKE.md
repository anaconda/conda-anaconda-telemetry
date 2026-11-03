# Spike: a vendor-neutral OTel plugin for `conda` with provider packages

Labels used in this document:
- **Verified** means tested, or read in the code or in the issue.
- **Recommended** means a judgement call that has not been tested.
- **Open** means someone else must answer it.

## 1. Summary

This spike recommends splitting the OpenTelemetry (OTel) code in `conda-anaconda-telemetry` (`CAT`) into a vendor-neutral plugin and separate provider packages, as proposed in [issue #127](https://github.com/conda/conda-maintainers-team-planning/issues/127).

- **Outcome.** A skeleton of the plugin ([`conda-otel`](https://github.com/lrandersson/conda-otel), short `CO`) and of the Anaconda provider ([`conda-otel-anaconda`](https://github.com/lrandersson/conda-otel-anaconda), short `COA`) works end-to-end with `conda` 26.7.2 against a local test server (**Verified**).
- **Recommendation.** The skeleton finds providers through an entry-point group. The recommended target is providers that are `conda` plugins. A native `conda` hook is also suggested, and that needs input from `conda` maintainers (**Recommended**).
- **Not ready for release.** The skeleton handles only `conda install`. It was tested only on Linux with a local test server, not with the production Anaconda endpoint. The default schema is only partly delivered, and the payload is smaller than the payload of `CAT` (**Verified**).
- **Privacy.** `CO` sends raw values to every provider, and each provider should redact them. The default of the `conda_otel` setting and the question of who opts in are compared in three options (section 5). Both affect user privacy, so the `conda` maintainers should make the choice with this spike's input (**Open**).
- **Decisions needed, and who answers each.**
  - How providers are found: the `conda` maintainers, who have not been asked yet (blocker 1, **Open**).
  - The privacy review of the data that `CO` gives to providers: probably also the `conda` maintainers (blocker 2, **Open**).
  - The default of the setting and who opts in: the `conda` maintainers, together with the privacy reviewer (blocker 2, **Open**).
  - The choices made while building the skeleton: the issue author should confirm them (section 4, **Open**).

## 2. Background

### What the issue asks for

Issue #127 proposes to replace the OTel code in `CAT` with two kinds of package:

- A vendor-neutral plugin, `CO`. It captures `conda` lifecycle events (commands, requested and resolved packages, channels, exceptions) with the official OTel SDK and passes them to registered providers.
- Provider packages that deliver events to a backend. Anaconda's endpoint, anonymous usage tokens and event schema move into `COA`. Others can write a provider for their own backend.

The issue also asks, "ideally", for a default event schema that providers can select from and override.

The spike has three deliverables: a skeleton of the plugin, a skeleton of the Anaconda provider, and this report. The plugin skeleton needs `conda` hooks that produce vendor-neutral events, provider discovery through an entry-point group, a bounded flush, and a `conda` setting to turn it on or off. The provider skeleton sends today's two install signals to Anaconda's endpoint. The report gives a recommendation, including whether `conda` should get a native `conda` hook instead of an entry-point group.

### Scope

- The HTTP header path of `CAT` is out of scope. The issue only concerns the OTel backend.
- A provider supplies an OTel exporter.
- Changes to `CAT` itself are not part of this spike.

### Constraints

These constraints apply to the new packages.

- The new core plugin (`CO`) is vendor-neutral. It holds no Anaconda endpoint, token or schema.
- Because `CO` is open source nothing secret can ship in it.
- Users can turn it off with a `conda` setting.
- A `conda` command must not halt when the network has problems. The issue asks for a bounded flush.
- Some users work in air-gapped or restricted networks, so a new endpoint may be blocked.

### Current behavior

The current `CAT` plugin hooks into `conda install` and `conda create`. It keeps the command, the names of the requested packages, the channels, and the resolved packages. It sends one of four signals: packages not found or success, each for install and create. The signals go through Anaconda's OTel wrapper, `anaconda-opentelemetry` (**Verified**).

Capture and destination sit in one place. The code that builds an event also holds the Anaconda endpoint, the anonymous usage tokens, and several workarounds for the wrapper. The workarounds hide OTel environment variables, flush on a background thread with a three second limit, turn off the wrapper's shutdown handling, and skip its connectivity check. The same code sets the policy for what may be sent: channels map to a fixed list, only package names are sent, and lists are cut to 50 items and 500 bytes.

No part can be reused without the rest. Another backend cannot use the capture code without taking Anaconda's destination logic with it.

## 3. What was built and verified

### What was built

The core plugin, `CO`, is a `conda` plugin. Hooks around `conda install` capture the channels, the requested packages, the resolved packages and, for a failed install, the packages that were not found. The plugin turns these into a vendor-neutral event and hands it to every installed provider. Each provider gets its own private OTel pipeline, so providers do not affect each other or other OTel users in the same process. After the event is sent, the plugin waits at most three seconds for delivery. The `conda` command then finishes, and any event that has not arrived by then is dropped. A `conda` setting, on by default, turns the plugin off. With no provider installed, nothing is captured. The plugin hides `OTEL_*` environment variables while it builds its objects, because a user setting could otherwise redirect or change the data. It never writes to the terminal.

A provider supplies an OTel log exporter, a set of resource attributes, and an optional step that changes the event for that provider only. The step can rename or add attributes, or drop the event.

The Anaconda provider, `COA`, maps the vendor-neutral events to the two install signals named in the issue, `install.pnfe` (here `pnfe` stands for packages not found error) and `install.success`. It sends them to Anaconda's endpoint through the standard OpenTelemetry Protocol (OTLP) HTTP log exporter, the same exporter that `anaconda-opentelemetry` uses, without the wrapper around it. The provider keeps the rules of `CAT`: channels map to a fixed list, and lists are cut to 50 items and 500 bytes. It uses the proxy settings of `conda` and sends the anonymous usage tokens, which it reads from the `anaconda-anon-usage` (AAU) package the same way `anaconda-opentelemetry` does. It also sends its own `client.sdk.version` (the version of `COA`), `schema.version` and `parameters` (an empty object) in place of the values that the wrapper adds.

The payload is a reduced version of today's. Parity with the `CAT` payload is not a goal of the skeleton. The skeleton does not yet send `conda.version`, `conda.ci_detected`, `os.version`, the installer attributes, `environment` or `service.instance.id`.

The channels differ from `CAT` on purpose. The plugin sends the channels from the `conda` configuration for both events. `CAT` does the same for a successful install, but for a packages-not-found error it sends the canonical channel names from the error. The new behavior makes the two events consistent.

### What was verified

The tests and checks ran on Linux with Python 3.11, `conda` 26.7.2 and OTel SDK 1.40.0. A GitHub action was also added to the two skeleton repositories to run the tests on Windows and macOS.

- The unit tests of both packages pass, also with `conda` 26.9.4 and OTel SDK 1.43.0.
- Both packages build as wheels and install with the expected entry points.
- Two providers run side by side. A slow provider does not block a fast one, and the flush ends within the time limit.
- The `OTEL_*` variables do not change the payload (see the end-to-end runs below).

The table shows the end-to-end checks (`conda install` with both packages installed), all run by hand. Both wheels were installed in a `conda` test environment, and the Anaconda endpoint was redirected to a local server that records OTLP requests. The appendix describes the procedure.

| Case | Result |
|---|---|
| Package not found, with and without `--dry-run` | One packages-not-found signal with the right attributes |
| Successful install | One success signal that includes the resolved packages |
| `--dry-run` or `--download-only` on a successful install, `conda create`, a spec that cannot be read, setting turned off | Nothing sent |
| Endpoint unreachable (closed port) | Install exits with code 0 and prints nothing extra |
| 18 `OTEL_*` variables set at once | Payload identical to a run without them |

The payload also carried seven of the eight anonymous usage tokens. The eighth, the Anaconda sign-in token, was missing because the tests ran without signing in.

### Not done

The skeleton is a proof of concept. These parts are left out on purpose or not tested:

- The production Anaconda endpoint was never tested. Every check used a local server.
- No `conda` package was built, and nothing ran on another operating system or another Python version. The end-to-end checks used one `conda` version and one OTel SDK version.
- Delivery over a network outside the local machine and through an actual proxy server was not tried. A closed port was tested. A slow or silent endpoint was not.
- The Anaconda sign-in token was not tested, because the tests ran without signing in.
- Only the `conda-forge` channel was used in the end-to-end checks. Unit tests cover the channel mapping.
- Flags other than `--dry-run` and `--download-only` were not studied.
- A provider built on the wrapper was not tried.
- The default schema exists only as a description. There is no schema file.
- No test covers error handling in four of the five hooks.

Section 7 lists these items as follow-up work, with a size for each. The skeleton is small to keep the review short.


## 4. Proposed design

### Who owns what

The core plugin, `CO`, captures `conda` events and dispatches them. Each provider owns its destination and its data policy.

The core plugin owns:

- the hooks and the vendor-neutral event
- the discovery of installed providers
- one private OTel pipeline per provider
- the time-limited flush
- the `conda` setting that turns everything off
- the isolation from `OTEL_*` environment variables
- the rule that nothing is written to the terminal

A provider owns:

- the endpoint and the proxy handling
- the redaction and the size limits
- the event names, the event name attribute and the schema version
- the resource attributes, including the service identity and any identifiers that the backend needs

The split fits because `CAT` mixes capture and destination (section 2), and different backends may need different policies. The Anaconda backend wants an unknown channel sent as `other`. A company with its own collector may want its internal channel names (**Recommended**).

The split has two consequences. First, the interface between `CO` and a provider is raw. A provider receives the values as `conda` holds them, and `CO` does not normalize or mask them. The channels are the strings from the `conda` configuration, and they can contain a credential, for example a token in a channel URL. Second, each provider must normalize and redact every value before it sends the data. A provider that skips this sends raw values. With no provider installed, `CO` captures nothing at all. Section 5 covers the privacy review.

### Default schema

The issue asks for a default schema that providers can select from and override. The proposal below builds on the vendor-neutral event that `CO` already produces. The skeleton implements the event part (**Verified**). The resource part is a proposal only (**Recommended**).

The plugin emits `install.success` and `install.packages_not_found`. A provider maps them to its own names. For `COA`, these are `install.success` and `install.pnfe`. Other commands would follow the same pattern.

| Default event attribute | Meaning | Name in today's `CAT` signal |
|---|---|---|
| `command` | The command that ran | `command` |
| `channels` | The channels used | `install.channels` |
| `channel_priority` | The channel priority setting of `conda` | `install.channel_priority` |
| `requested_packages` | The package names the user asked for | `requested.packages` |
| `resolved_packages` (success only) | The packages that are installed | `resolved.packages` |
| `missing_packages` (not found only) | The package names that were not found | `exception.missing_specs` |
| `exception_name` (not found only) | The type of the error | `exception.name` |

The default resource attributes are neutral facts about the machine: the `conda` version, the operating system type and version, the Python version, and whether a CI environment was detected. The plugin would add them under the attributes of the provider. If both set the same attribute, the value from the provider wins.

This part is not implemented yet. The provider sets the operating system type and the Python version itself, and nothing sets the other three.

The provider owns everything else:

- the attribute names and the size limits: the dotted names, the schema version, an attribute that says whether a list was shortened, the channel list, and the limits of 50 items and 500 bytes
- the identity of the backend: service name and version, platform, environment and instance ID
- the SDK version attributes
- any identifiers that are specific to the backend. For `COA`, these are the anonymous usage tokens.

A provider selects and overrides in two ways. A step receives the default event and returns any event. It can rename or add attributes, or drop the event. The resource attributes of the provider override the default ones.

The proposal has two caveats. The plugin applies no redaction. Attribute values must be scalars or lists of one scalar type.

Two changes would make the schema easier to review (**Recommended**). The first is a versioned schema file in `CO`, as `CAT` already has [one](https://github.com/anaconda/conda-anaconda-telemetry/tree/main/schema). The second is to follow the OTel semantic conventions.

### What replaces the wrapper

Today `CAT` depends on `anaconda-opentelemetry`. The table lists what that wrapper does for `CAT` and what replaces it. The interfaces are proposals. Only the pieces marked below were built.

| Wrapper behavior | Replacement | Owner | Status |
|---|---|---|---|
| Creates a global OTel logging provider | A private provider for each provider package, never set as global | `CO` | **Verified** |
| Batches log records, with a wrapper around the exporter so the endpoint can change | A batch processor in `CO` with the standard OTLP HTTP log exporter from the provider | `CO` and provider | **Verified** |
| Adds the log path to the endpoint and builds a proxy session | The provider does both, using the proxy settings of `conda`. A unit test covers this. No actual proxy server was tried. | Provider | **Verified** |
| Checks the connection before starting | Nothing. The standard SDK does not check. | None | **Verified** |
| Hides `OTEL_*` variables on request. The `CAT` plugin adds its own hiding. | Two layers in `CO`: hide the variables while objects are built, and set explicit record limits. Manual tests with 18 variables cover this. | `CO` | **Verified** |
| Sets the event name attribute and filters values to scalars and lists of scalars | A small emitter in `CO`. It sets the event name field of the log record. The provider adds an event name attribute, as `CAT` signals have. | `CO` and provider | **Verified** |
| Workarounds in `CAT` for flush and shutdown: a background thread, a 3s wait, no shutdown on exit | A time-limited flush in `CO`. A slow delivery is dropped. Unit tests and a manual test with a closed port cover this. A slow or silent endpoint was not tested. | `CO` | **Verified** |
| Uses private OTel APIs, with a version pin and a no-op fallback | The same private APIs, with a version pin (SDK 1.40 up to below 1.44) and no fallback. See section 6. | `CO` | **Open** |
| Builds the resource: renames keys, adds the SDK and schema versions, encodes `parameters`, loads the eight anonymous usage tokens | A resource builder in the provider. This is the largest piece. The tokens and the version attributes are sent. Several current attributes are not yet sent (section 3). | Provider | **Recommended** |

### Decisions made in the skeleton

These choices were made while building the skeleton. All are **Recommended**. The issue author should confirm them, and none blocks further work.

| Decision | Reason |
|---|---|
| No Anaconda-specific code in `CO` | The issue says the core is vendor-neutral and that endpoint, tokens and schema move to the provider. |
| The core plugin depends only on the OTel SDK. The exporter belongs to the provider. | The issue names the coupling to the wrapper as the problem. That `CO` must not depend on the wrapper is a reading of the issue, not a literal statement. |
| The provider owns the channel list, the list limits and the schema version | Each provider needs its own policy, as in the example above. |
| Each provider gets a private OTel pipeline that is never global | This avoids conflicts with other OTel users in the same process. |
| A slow delivery is dropped. There is no background process and no disk queue. | A background process can outlive the environment it runs from, and it shows in the process list. A disk queue keeps unredacted data on disk, and channel URLs can contain tokens. The user waits at most 3s. |
| The plugin never writes to the terminal | Without this, OTel errors reach stderr. With a closed port, `conda` printed errors until this was added. |
| The `CO` setting is on by default | The setting of `CAT` is on by default. |
| The old plugin `CAT` and `CO` are not meant to be installed together | Both emit the install signals, so installing both would send each event twice. Because the two are not installed together, the design needs no rule for how they interact. |
| The provider can set `client.sdk.version`, `schema.version` and `parameters` itself | The wrapper sets these values and they describe the wrapper. Neither package depends on the wrapper, so each provider decides what to send. |
| Payload parity is not a goal of the skeleton | The `CAT` plugin and its schema already define the contract. The skeleton shows the structure. |
| The name `conda-otel-anaconda` is a working name | It follows the pattern `conda-otel-<vendor>`. It may be confused with `anaconda-opentelemetry`, so the name must always mark it as a provider of `CO`. Both package names were free on PyPI, conda-forge and `main` when last checked in October. |

## 5. Decisions needed

Two blockers need an answer from other people. Neither affects the skeleton or this report, but both block a release.

### Blocker 1: how providers are found

`CO` can find providers through an entry-point group, through providers that are ordinary `conda` plugins, or through a native `conda` hook. The `conda` maintainers should help choose (**Open**).

| Option | How it works | Pros | Cons | Status | Verdict |
|---|---|---|---|---|---|
| A. Entry-point group | The plugin looks for provider packages in its own entry-point group | Works with today's `conda`. Providers load only when the setting is on, and only for `conda install`. | A provider has no settings of its own, so there is no per-provider opt-in and no endpoint override. Not releasable if per-provider opt-in is required. | **Verified** | Not **Recommended** |
| B. Own extension point in `conda` | The plugin adds its own extension point to the plugin manager of `conda`. A provider is then an ordinary `conda` plugin. | Needs no change in `conda`. A provider can register its own setting. | The `conda` tool loads every plugin entry point on each command, so provider modules import each time. A manual test with `conda` and two small stand-in packages measured about 0.03 s, within noise on one machine. It was not tried with the actual packages. | **Verified** | **Recommended** |
| C. Native `conda` hook | The `conda` tool itself defines a hook for telemetry sinks | The interface belongs to `conda`. | Needs a `conda` change, perhaps also a `conda` enhancement proposal (CEP). | **Open** | **Open** |

The recommended order: first move to option B, so that a provider is an ordinary `conda` plugin with its own setting and opt-in. Option A stays only as the mechanism of the skeleton. Then, if `conda` maintainers agree, move to option C. A small provider interface keeps the move from A to B or C cheap. Work can continue in the meantime, because the skeleton already uses option A.

### Blocker 2: privacy review

A privacy review must cover the fields that `CO` gives to every provider before `CO` or any provider is released. The fields are the package names, the channels, the channel priority and the error type. The plugin applies no redaction, so a provider with weaker rules could send more than intended. The reviewer must know which data that `conda` handles may be private (**Open**).

The interface between CO and a provider is raw, and each provider must remove sensitive data (Recommended). How much more it removes depends on its backend. A provider for an internal collector may keep internal channel names. A default rule in CO, for example a fixed channel list, was considered and is not recommended. It puts policy in CO, and a provider that needs raw values cannot get them.

Two more questions affect user privacy: whether the setting is on or off by default, and who opts in. The author of the issue should discuss the options below (**Open**).

| Option | Pros | Cons |
|---|---|---|
| On by default, and installing a provider is the opt-in (the skeleton) | Same as `CAT` today. No extra work. | Data can flow after an install that the user did not see as consent. |
| Off by default, and one `conda` setting turns on all providers | Cheap. Works with the entry-point group. | One switch for all providers. The user cannot pick a provider. |
| Off by default, and one setting per provider | The user picks each provider. | Providers must be `conda` plugins (the plugin option in blocker 1). More work. |


### How the Anaconda provider is built

The skeleton sends data through the standard OTLP HTTP log exporter. The alternative is to keep `anaconda-opentelemetry` inside the provider.

| Option | Pros | Cons | Status | Verdict |
|---|---|---|---|---|
| Standard exporter | No dependency on the wrapper. No global OTel provider and no connection check. | The provider needs its own resource builder. | **Verified** | **Recommended** |
| Existing wrapper inside the provider | Reuses the resource builder of the wrapper. | Keeps the coupling that the issue wants to remove. The workarounds in `CAT` stay. Not tried. Only an option if payload parity shows a gap that the resource builder cannot close. | **Open** | Not **Recommended** |

### Smaller decisions for the team

Each of these is open.

- Disabling the plugin via `OTEL_SDK_DISABLED`. The plugin ignores the variable on purpose. It hides all `OTEL_*` variables so that a user setting cannot change where data goes. The options are to keep ignoring it, or to honor it as an off switch only. The recommendation is the second option, because it cannot redirect any data (**Recommended**).
- Fork or install. A company may fork a provider, or install an existing one and change its rules, for example the channel list. A forked provider needs only code. An installed one needs a settings surface and a default. The spike records both and does not choose.

## 6. Risks, open problems and unverified assumptions

Section 5 covers the privacy review, provider opt-in and `OTEL_SDK_DISABLED`, because they are decisions. The fixes below are **Recommended**.

| Risk | What could go wrong | How to confirm or fix |
|---|---|---|
| Baseline payload | The skeleton sends a reduced payload, and the backend may need attributes that are missing, such as the `conda` version, the operating system version and the installer attributes. | The team agrees on the baseline payload that a provider sends by default. |
| Proxies that re-sign HTTPS traffic | Delivery may fail behind such a proxy, because the provider does not read the `conda` setting `ssl_verify`. An `HTTP_PROXY` variable in the environment also takes precedence over the proxy setting of `conda`. | Test with an actual proxy server, with and without re-signing. Pass the `ssl_verify` setting of `conda` to the HTTP client. Decide which proxy setting takes precedence. |
| Slow or unreachable endpoint | Every `conda install` can wait up to 3s, and the event is lost if delivery takes longer. Only a closed port was tested, not a slow or silent endpoint and not a network outside the local machine. | Measure with a delayed endpoint and over a network outside the local machine. Shorten the time limit, or accept the loss. |
| Private OTel APIs | The plugin uses private parts of the OTel SDK. The unit tests ran with SDK versions 1.40.0 and 1.43.0 only, and a new release could break it. The version pin limits the risk but gives no fallback. | Run the tests against each supported SDK version. Keep the pin and add a fallback, or stop using private APIs. |
| Other `conda install` flags | Flags other than `--dry-run` and `--download-only` may change what a successful install means, so the plugin could report an install that did not happen. | Review the flags of `conda install` and handle the ones that change the result. |
| Platforms and packaging | Only Linux and Python 3.11 were tried, and no `conda` package exists. | Build the `conda` package and test on other operating systems and Python versions. |

These assumptions are not verified:

- An entry-point group is enough for the skeleton. Whether it is enough for a first release depends on the opt-in decision (blocker 1). The discussion with the `conda` maintainers can confirm it.
- When `conda` retries a solve, the last list of requested packages is the right one. This was read in the `conda` source and not run. A run where the first solve attempt fails can confirm it.

## 7. Next steps

The order and the sizes are **Recommended**. The sizes are guesses for one engineer: S is up to about 3 days, M is about 1 to 2 weeks, and L is more than 2 weeks.

### Can start now

| Work item | Size | Depends on |
|---|---|---|
| Discuss the discovery mechanism with the `conda` maintainers (blocker 1) | S | Nothing |
| Name a reviewer and run the privacy review (blocker 2) | S to M | Nothing. The size depends on the reviewer. |
| Agree on the baseline payload that a provider sends by default | S | Nothing |
| Review the flags of `conda install` and handle the ones that change the result | S | Nothing |
| Declare a package conflict between `CAT` and `CO`, so that both cannot be installed together | S | Nothing |
| Build option B: providers as `conda` plugins, with their own settings and opt-in | M | Nothing |

### Waits for a decision or for earlier work

| Work item | Size | Depends on |
|---|---|---|
| Move the code to its own repositories in `conda-incubator`, with CI and checks | M | The team review of this spike. The name `conda-otel-anaconda` should be confirmed first. |
| Add the baseline payload to `COA` and the default resource attributes to `CO`, then test against the production Anaconda endpoint and verify the payload with the team that handles the data. | M | The agreed baseline payload and access to the endpoint |
| Test delivery with a slow endpoint, over a network outside the local machine and through proxies, including HTTPS re-signing, and pass the `ssl_verify` setting of `conda` to the HTTP client | M | The new repositories and a proxy that re-signs HTTPS traffic for testing |
| Build the `conda` package, test on other operating systems and Python versions, and run the tests against each supported OTel SDK version | M | The new repositories and CI |
| Write a versioned schema file for the default event and resource attributes, and check the attribute names against the OTel semantic conventions | S | The agreed baseline payload |
| Extend the capture to `conda create` and other commands | S per command | The agreed baseline payload |
| Migrate from `CAT` to `CO` and `COA`. | M | A release of both packages, the privacy review, and the test against the production endpoint |

## 8. Appendix

### Where things are

- This document and `ARCHITECTURE.md` are submitted for review in the repository of `CAT`. The architecture document has the diagrams, the data flow and the numbered list of gaps.
- The code of `CO` (https://github.com/lrandersson/conda-otel) and `COA` (https://github.com/lrandersson/conda-otel-anaconda) starts in personal repositories under the `lrandersson` GitHub account. Each repository has a short README and a GitHub Actions workflow that runs the tests with `conda` 26.7 and Python 3.14 on Linux, Windows and macOS. Eventually `conda-incubator` should be considered instead.

### Sources

- [Issue #127](https://github.com/conda/conda-maintainers-team-planning/issues/127)
- [`CAT`](https://github.com/anaconda/conda-anaconda-telemetry), including the signal schema in its `schema` directory
- [`anaconda-otel-python`](https://github.com/anaconda/anaconda-otel-python), the source of the `anaconda-opentelemetry` wrapper

### Issue items and where they are answered

| Item in the issue | Section |
|---|---|
| Plugin skeleton: hooks that produce vendor-neutral events | 3 and 4 |
| Plugin skeleton: provider discovery through an entry-point group | 3 and 5 |
| Plugin skeleton: bounded flush | 3 |
| Plugin skeleton: `conda` setting to turn it on or off | 3 |
| Provider skeleton: sends today's install signals to the Anaconda endpoint | 3 |
| Default schema that providers can select from and override | 4 |
| Coupling to the wrapper and its workarounds | 2 and 4 |
| Others can write a provider for their own backend | 4 and 5 |
| Report with a recommendation | 1 and 5 |
| Native `conda` hook instead of an entry-point group | 5 (blocker 1) |

### How to reproduce

The tests and checks ran on Linux with Python 3.11, `conda` 26.7.2 and OTel SDK 1.40.0.

For unit tests, each repository has an `environment.yml` file. Then run `pip install -e .` and `python -m pytest` in each repository. The `pytest` version is pinned to below 9.1 because `pytest` 9.1 and newer fails, and this spike leaves that fix out. The plugin itself is not affected. GitHub Actions runs the same steps in both repositories.

The end-to-end checks were run manually, and no scripts were kept. The steps were:

1. Create the test environment.
2. Build a wheel of each package and install both wheels into the copy, without their dependencies.
3. Start a local HTTP server that accepts POST requests on the log path and records the OTLP payload of each request.
4. Point the provider at the local server. The provider takes its endpoint as an argument only for tests, so a small start-up script replaced the default endpoint. The script is not part of the packages.
5. Run `conda install` for each case in the table of section 3, count the recorded requests after each run.
6. For the unreachable endpoint, point the provider at a closed port. For the `OTEL_*` check, set the 18 variables, repeat one run, and compare the recorded payload with a run without them.

For the manual test of option B, two small packages were written by hand. One stands in for the plugin and adds its own extension point to the plugin manager of `conda` on first use. The other is a provider that registers as an ordinary `conda` plugin for that extension point. Running `conda info` with both installed showed the provider results. Running it with only the provider installed gave no error. For the import cost, `conda info` ran six times with and without the module of the Anaconda provider registered as a `conda` plugin, and the run times were compared.
