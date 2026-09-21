# Changelog

## 0.3.1 - 2026-09-21

### Fixed

- Import conda plugin types from `conda.plugins.types` so the plugin loads with
  conda 26.9 and later (#222).
- Remove authentication credentials from channel URLs included in telemetry
  headers (#217).

### Compatibility

- Require Python 3.10 or later (#165).
- Add Python 3.14 and conda 26.7 compatibility coverage (#249).
- Test plugin entry-point loading against the conda development canary (#249).

[0.3.1]: https://github.com/anaconda/conda-anaconda-telemetry/compare/0.3.0...0.3.1
