# OTel signal schema

This folder describes the OpenTelemetry (OTel) data that `conda-anaconda-telemetry`
sends. It has two hand-edited JSON files:

| File | Purpose |
|:-----|:--------|
| `signal_schema.json` | A sample signal, listing each attribute and its format. |
| `signal_schema_description.json` | Plain-language text and metadata for every attribute and event. |

This folder is not part of the distributed plugin but exists for the purpose of explaining the collected telemetry.

## For users

- The sample and the description are the source of the OTel section in
  [`docs/faq.md`](../docs/faq.md). Read the FAQ for a fully rendered version.
- `signal_schema.json` shows which attributes exist. Values like `"<string>"` are
  placeholders, not real data.
- `signal_schema_description.json` tells you, for each attribute:
  - what it discloses,
  - under which condition it's being sent (`optional` and `condition`),
  - for `aau.*` tokens (from `anaconda-anon-usage`), the kind of token
    (`token_class`: `persistent`, `per-run` or `account-linked`). `aau.version` is a
    version string.
- Four events exist: `install` and `create`, each with a `pnfe`
  (package not found) and a `success` outcome. Each description lists when the
  event is not sent.

## For developers

### Purpose and consistency

The two `signal*.json` files are the single source of truth for what the plugin discloses through OTel.
The files, the real export and the FAQ must agree. This is enforced via tests and a pre-commit hook:

- `tests/test_signal_schema.py` checks that the two files match each other and the
  supported commands.
- `tests/test_otlp_integration.py` compares the real OTLP export of all four events
  to the sample.
- `tests/test_resource_attributes.py` checks that the optional resource attributes
  (`installer.*`, `aau.*`) stay within the schema.
- `scripts/update_docs.py` renders the FAQ section between the
  `GENERATED OTEL SIGNAL` markers. Do not edit that section by hand.

### Formats

`signal_schema.json`:

```
{"resource": {<key>: <value>}, "events": {<event name>: {<log key>: <value>}}}
```

- A string like `"<...>"` is a placeholder and is not compared.
- Any other string is a fixed value and is compared exactly.
- Lists, booleans and numbers are never compared by value.

`signal_schema_description.json`:

```
{"events":   {<event name>: {"description": str}},
 "resource": {<key>: {"description", "owner": "plugin"|"sdk", "optional": bool,
                      "condition" (only if optional), "token_class" (aau.* only)}},
 "log":      {<key>: {same as resource, no token_class, optional "outcomes": ["pnfe"|"success"]}}}
```

Omitted `outcomes` means the attribute is sent for both outcomes.

### Common tasks

Running from the repository root, using `python` or `pytest`, you can:

- Regenerate the FAQ after you edit a schema file:

  ```
  python scripts/update_docs.py
  ```

- Check that the FAQ is current (the `faq-signal-docs` pre-commit hook does this):

  ```
  python scripts/update_docs.py --check
  ```

- Update `signal_schema.json` after a signal change. The export test then
  rewrites the sample from the observed key names (values are never copied):

  ```
  UPDATE_SIGNAL_SCHEMA=1 pytest tests/test_otlp_integration.py
  ```

  Review the diff, add the matching entries to `signal_schema_description.json`,
  then regenerate the FAQ. Note: resource attributes are read from the first exported
  record only. Do not set this variable in the CI environment because it will hide any potential drift.

- When you add a new attribute, add it to both files, and set `owner`
  (`plugin` if this repository supplies the value, `sdk` if `anaconda_opentelemetry`
  does). Check the source: for example, `log.event.name` is `sdk`, and `environment`
  is `plugin` because the plugin sets it.
