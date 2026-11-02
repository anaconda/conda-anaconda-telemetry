# Spike: Using feature flags in conda-anaconda-telemetry

## Introduction

[Issue \#91](https://github.com/anaconda/conda-anaconda-telemetry/issues/91) ("Add feature-flag support using Eppo") asks for a way to roll out the OpenTelemetry (OTel) backend of `conda-anaconda-telemetry` (CAT) gradually. The issue originally requested to use Eppo, but Anaconda is currently phasing out Eppo for LaunchDarkly (LD). The ticket does not require LD. The actual need is a remote way to enable and disable the OTel backend. This document examines how that can be done and recommends one direction.

The scope is architecture and viability only. Questions about who creates and owns the flag in LD, who runs the rollout, and who manages access stay with Data & Analytics (D\&A). They are not covered here.

### Constraints

- **Response time/Time to take effect.** A change must take effect in hours, not in a release cycle.  
- **Nothing secret on user machines.** CAT is open-source and distributed through the `main` channel and as part of the Anaconda installers (Miniconda and Anaconda Distribution). Users receive the code and can inspect it. Any value that ships with CAT must be treated as readable by anyone.  
- **Restricted networks.** Users include air-gapped and strict-network environments. Some of them only allow outgoing connections to an approved list of hosts. For these users, a host that they do not already reach may be blocked or may need approval first. Not all users are affected. If the flag cannot be read, CAT must fail closed, which means the OTel backend does not send data.  
- **Not a security control.** The flag is a rollout gate. Users can already turn telemetry off with a conda setting.

### Current behavior

CAT has two telemetry variants. Both run when telemetry is enabled. One variant adds HTTP headers (considered legacy) to conda's repository requests and will be phased out in favor of OTel. The other new variant sends data through OTel. The flag only needs to enable or disable the OTel variant. However, the direction suggested in this document is valid for either backend and not specific to OTel.

## Options

Below is a list of the explored options, each discussed further below. Claims about LD come from LD documentation and from a meeting with LD representatives. They were not tested. The response times for options 1 to 6 are expected values and were not measured.

| Option | Response time | Secret needed | New destination | Verdict |
| :---- | :---- | :---- | :---- | :---- |
| 1\. LD Python SDK, key shipped | Minutes | Yes, shipped | LD | Not viable |
| 2\. LD Relay Proxy alone | Minutes | Yes, shipped | Anaconda host | Not viable |
| 3\. LD client-side ID or mobile key | Minutes | No | LD | Closed |
| 4\. Compiled binary with embedded key | Minutes | Yes, shipped | LD | Not viable |
| 5\. Anaconda-hosted service returning a boolean | Minutes | No (held server-side) | Anaconda service | Viable, not preferred |
| 6\. Self-hosted flagd | Minutes | No | Anaconda service (hosted) or none (file) | Same as 5, or converges with 8 |
| 7\. Release-based rollout | Release cycle | No | None | Fallback |
| 8\. Published rules file | Hours (depends on CDN cache) | No | None new if the user already reaches `repo.anaconda.com` | Recommended |

### LD Python SDK with a shipped key (option 1\)

Not viable. The Python SDK is a server-side SDK. LD states that server-side SDKs are for "*a trusted environment*" and that the SDK key "*should be kept a secret*", because it exposes the full ruleset of the environment. LD support gave the same answer for this use case: the key must stay private, even when it is rotated regularly. Source: [LD, choosing an SDK type](https://launchdarkly.com/docs/sdk/concepts/client-side-server-side). CAT runs on user machines (and is open-source), so the key would be exposed.

### LD Relay Proxy alone (option 2\)

Not viable. In proxy mode, the Python SDK still needs the SDK key in its configuration, together with the addresses of the proxy. A proxy therefore does not remove the key from the client. Source: [LD, proxy mode](https://launchdarkly.com/docs/sdk/features/relay-proxy-configuration/proxy-mode).

### LD client-side ID or mobile key (option 3\)

Closed. These keys are public by design. However, LD enforces the key type for each SDK type, and no Python client-side SDK exists. A client-side ID used with the Python server SDK is rejected.

### Compiled binary with embedded key (option 4\)

Not viable. A binary shipped as part of CAT, called by CAT as a separate process, would hold the key and the network call. The binary runs on the user machine. A user can recover the key by searching the binary for text, with a debugger, or by reading the authorization header of the request through a proxy that intercepts TLS traffic. This does not solve the issue with the secret key.

### Anaconda-hosted service (option 5\)

Technically viable. A service run by Anaconda holds the LD key, evaluates the flag and returns a boolean. A caller gets one boolean for one flag, not the key. The remaining risk is ordinary API abuse. It is not the preferred direction since:

- Anaconda must build and run a service.  
- It adds a new host that CAT must reach (once per cache period). Users on restricted networks may block it or need to approve it first.  
- The address is not secret, so anyone can call it.

Option 8 keeps the same idea (a small remote answer fetched by CAT) but serves a static file instead of running a service.

### Self-hosted flagd (option 6\)

flagd is an OpenFeature-native flag evaluator. It has two variants:

- **Hosted service.** The shape is the same as option 5, and so is the verdict.  
- **In-process, reading a flag-definition file.** This converges with option 8, because the file is the transport. flagd would only evaluate the rules. It would add the OpenFeature SDK and a provider as new dependencies, which would also need packaging on `main`. 

The maturity of the Python in-process provider and its HTTP sync and cache behavior were **not investigated**.

### Release-based rollout (option 7\)

The package ships with the OTel backend off by default. A new package version or installer turns it on. Staged channel publishing gives a gradual ramp. A kill switch needs a new release. This approach already exists today: CAT is released with the Anaconda installers, thus a new CAT version or installer has the option to modify the behavior. It is rejected as the main direction because a change requires a new package or installer, which does not meet the required response time of hours.

### Published rules file (option 8\)

Anaconda publishes a static rules file. CAT fetches it. This is the recommended direction and is described in the next section.

### Similarity to `conda notices`

Option 8 follows an approach that conda already uses for `conda notices`. A notices file is a static, read-only JSON file served by channel infrastructure. conda fetches it with no SDK and no credential. The mechanism was examined in conda 26.7.2:

- conda fetches the notices file with a plain GET request through its own session, with a 5 s timeout and a cache. On error it logs and skips the channel. No SDK or credential is involved (verified in conda 26.7.2).

From this analysis, a similar approach looks feasible for the flag. CAT would fetch a small static file in the same way and fail closed if the fetch does not work. The analysis is limited. The cache time of notices and the exact conditions that enable the notices fetch were not read in detail.

Reusing `conda notices` itself is a different question. Notices are built from each user's channels, and Anaconda does not control conda-forge or customer mirrors. The fetch only runs when the user has notices enabled. Notices are also a user-facing feature that belongs to other teams. Whether to reuse the feature, or only copy its approach with a separate file, needs a decision from the owners of `conda notices` and from the people who run the Anaconda channels. This document does not make that decision.

## Recommended direction: a published rules file

Anaconda publishes a non-secret rules file at a fixed address, for example `https://repo.anaconda.com/pkgs/main/flags.json`. The exact location is an example. Whether Anaconda can publish a file there is not verified (see the identified gaps). Note that a more generalized direction is also described in the Section [“Applying the approach to other conda plugins”](#applying-the-approach-to-other-conda-plugins).

### Why it fits the constraints

- **No secret.** The file is public by design, like repodata.  
- **No new network destination for users who already reach `repo.anaconda.com`.** Users who only use other channels or a mirror may not reach it. For them CAT fails closed (see below).  
- **No new hosting.** It is a static file, not a service.  
- **No persistent connection.** CAT makes one cached `GET` request. No SDK and no background threads are involved.  
- **Response time of hours.** Anaconda edits and republishes the file. CAT picks the change up after the local cache time expires.  
- **Air-gapped and mirrored users.** The fetch fails or reaches a stale copy, and CAT fails closed. This is acceptable because these machines likely cannot reach the OTel backend either.

### Intended CAT behavior

This is the intended shape and not a finished design. Note that this can be applied also to other plugins or features by Anaconda in the future.

- CAT fetches the file with conda's own session, a short timeout and a local cache with a short lifetime.  
- The file holds the rule and a staleness marker, for example an enabled switch, a percentage (more on that later) and an update or expiry time. The format is not final. CAT treats an expired file as "off". This covers stale mirror copies that still say "on".  
- CAT fails closed on every error: timeout, invalid JSON, missing file, missing entry and expired file.  
- CAT evaluates the flag once per process, so the checks before and after a command agree within one run.  
- The check runs after CAT has confirmed that telemetry is enabled, and before any OTel data is sent. The fetch must not delay commands such as `conda install`, so CAT owns the timeout.  
- Users must not be able to override the address or the file through configuration or environment variables. CAT already prevents redirection of the OTel backend through environment variables, and the flag needs the same protection.

### Cost

There is no live LD dashboard and no instant toggle. A change takes effect after republishing plus the cache time. LD, if used at all, is only an internal tool to author the file. It is not needed.

## Evaluation context

This section explains how to roll out the plugin only to a subset of users who have the plugin installed and enabled. This is completely optional but included in this document to highlight that it is still technically possible.

Continuing on the idea of using a published file, this file can **also** list the percentage of invocations that should send OTel data. CAT must decide, on each machine, whether a given invocation is in that percentage. Two approaches were considered.

- **Per-invocation random draw (recommended).** CAT draws a random number and enables OTel if the number is below the published percentage.  
- **Persisted identifier.** CAT turns a stored identifier into a bucket, so a given machine always gets the same answer.

The random draw is recommended for these reasons:

- The flag is a gradual ramp and a kill switch. It is not an experiment that compares groups of machines. For a ramp, the overall share of invocations is what matters, and a random draw gives this share.  
- It needs no identifier. A persisted identifier is a new data item, and using it for this purpose would probably need a privacy review. Reusing an existing identifier would not remove that need if it were sent to a third party. A random draw avoids the question.

The downside with this approach is that one machine can be "in" for one command and "out" for the next. For a telemetry ramp this is acceptable. If a later feature needs the same answer on each run, CAT can switch to a persisted identifier. The file format does not need to change. D\&A can choose the persisted approach now if this behavior is not acceptable.

## Applying the approach to other conda plugins {#applying-the-approach-to-other-conda-plugins}

The recommended direction does not depend on CAT and can be generalized. Any open-source conda plugin has the same problem: it cannot ship a secret, and it still needs a way to enable or disable a feature after release. As an example we can consider a future `conda-otel` plugin. This section describes the approach in general terms and should be considered as a starting point for an idea \- not a finished design.

### Plugin contract

A plugin that uses a published rules file follows these rules:

- The feature is off by default.  
- A local user setting that turns the feature off has priority over the file. The file can only reduce what a plugin does. It cannot override user consent.  
- The plugin has a default address for the file. Only the party that deploys the plugin can change it. Users cannot change it with user-level settings or environment variables. This prevents an unrelated party from redirecting the file and turning a feature on.  
- The plugin uses conda's own session, a short timeout and a short local cache.  
- The plugin treats every error as "off": timeout, missing file, invalid content, missing entry and expired file.  
- The plugin evaluates the rule once per process.  
- The file holds rollout settings only, for example an enabled switch, a percentage and an expiry time. It holds no user data and no rules that select specific users or machines. It can **only** turn on or off behavior that is already in the released plugin.  
- Each plugin has its own file, or its own namespace in a shared file. An edit for one plugin must not break another plugin.

### Hosting

The main open question is where the file lives. Options:

| Location | Benefit | Cost |
| :---- | :---- | :---- |
| Channel path on `repo.anaconda.com`, next to `terms.json` (as `conda-anaconda-tos` does) | No new host for users who already reach the channel. Same operations as an existing file. | Only works for plugins that Anaconda owns. Other plugin owners cannot publish there. How `terms.json` is published is not verified. |
| Static file on GitHub (raw or Pages) | Public and reviewable. Each change is a pull request. Plugin owners control it. | A new host for users. Need to consider restricted networks. Cache and rate limits are outside Anaconda's control. |
| Organization mirror or internal host | An organization controls the rollout for its own users. No new host, and it works on restricted networks. | Each organization must host and maintain its own file. If the file is missing, the feature stays off. |
| Host managed by conda infrastructure | One shared place for all conda plugins. | Needs an infrastructure request, an owner and a process. |

An organization that deploys the plugin can point it to its own file, for example on its internal mirror. In that case Anaconda does not control the rollout for that organization. If an organization changes the default address, the feature stays off until the organization provides a file at the new address, unless the plugin owner decides otherwise. Whoever can edit the file controls the rollout.

### Shared code

Each plugin needs the same small logic: fetch, cache, expiry check, fail closed and an optional random draw. Plugins can each implement it, or utilize a small helper package. Part of this logic already exists in `conda-anaconda-tos`. Whether to share it is a later decision.

### Limits

- The file is a rollout gate. It is not a security control.  
- It cannot enable a feature for specific users or machines, and it cannot compare groups of users in an experiment. It only sets one on/off state and one percentage for all users.  
- A change takes effect after republishing plus the cache time. It is not instant.  
- Users on air-gapped or mirrored networks may never receive the flag. For them the feature stays off.

## Identified gaps

Other teams must confirm the following points.

- **Publishing.** Who can publish a file to `repo.anaconda.com/pkgs/main/`, who owns it, and whether the channel pipeline accepts an arbitrary file name. Not verified.  
- **Content delivery network cache.** The cache time on that path sets the real response time.  
- **Mirrors.** Customer mirrors that sync `main` may serve a stale copy or none. The staleness marker and the fail-closed behavior cover the risk. The effect on rollout reach should still be known.  
- **OpenFeature.** The option set also applies to a possible separate plugin that offers flag evaluation to other plugins through OpenFeature. Such a plugin would not remove the secret problem. It would only move the responsibility to each adopter. A default provider that calls an Anaconda-hosted endpoint would commit Anaconda to run shared flag infrastructure. This is out of scope here.  
- **`conda notices`.** Whether to reuse `conda notices` or copy its approach with a separate file needs a decision from the owners of `conda notices` and the people who run the Anaconda channels.  
- **No measurements.** Fetch latency, cache behavior and failure timing has not been investigated as part of creating this document, but something to consider. Even if the spike concluded that LD could be used, this would still have been a real risk that required further investigation.  
- **Packaging.** The LD and flagd options need `launchdarkly-server-sdk` or the OpenFeature packages on `main`. `launchdarkly-server-sdk` is on conda-forge as version 9.18.1, with the dependencies `launchdarkly-eventsource`, `expiringdict`, `pyrfc3339`, `pytz` and `semver`. Which of these are missing from `main` was not checked. Option 8 needs no new dependency.  
- **Behavior without a rollout file (for the generic rollout approach).** If an organization changes the default address and provides no file, the plugin owner must decide whether the feature stays off or follows only the local user setting.  
- **LD ownership.** Who creates and owns the flag, who runs the rollout, and who manages access stay with D\&A.

## Conclusion

LD cannot be used from the client. The key must stay private, and CAT runs on user machines. Every way to use LD without shipping the key needs Anaconda to host something, which may also conflict with air-gapped and strict-network users.

The recommended direction is a published rules file at a fixed address. CAT fetches and caches it, evaluates it with a per-invocation random draw (optional), and fails closed. It is the only option that combines no secret, no new hosting and no persistent connection with a change within hours. Release-based rollout (option 7\) has the same first three properties but fails on response time. The in-process flagd variant converges with this option.

If Anaconda cannot publish such a file, release-based rollout (option 7\) seems like the best option given all of the constraints.  
