# Manual Testing

This document is for manual integration testing. It is organized according to the
release version. It contains commands to run and shows what should be included in
the request headers.

## Version `0.1.0`

### Setup

Make sure to begin with a new Miniconda install, and follow these steps:

Install the latest development version of conda:

```commandline
conda install conda-canary/label/dev::conda
```

Clone this repository locally:

```
git clone git@github.com:anaconda/conda-anaconda-telemetry.git
```

Use pip to install the plugin:

```commandline
pip install -e conda-anaconda-telemetry
```

### Tests

All the tests should be run with the `-v -v -v` flags so that the headers can be inspected.

#### Test to ensure search terms are being submitted

Test command:

```
conda search conda -v -v -v
```

Expected headers

```json
{
  "User-Agent": "conda/24.9.3.dev35 requests/2.31.0 CPython/3.12.2 Darwin/23.4.0 OSX/14.4.1 solver/libmamba conda-libmamba-solver/24.1.0 libmambapy/1.5.8 aau/0.4.4",
  "Accept-Encoding": "gzip, deflate, br, zstd",
  "Accept": "*/*",
  "Connection": "keep-alive",
  "Anaconda-Telemetry-Channels": "https://repo.anaconda.com/pkgs/main/osx-arm64;https://repo.anaconda.com/pkgs/main/noarch;https://repo.anaconda.com/pkgs/r/osx-arm64;https://repo.anaconda.com/pkgs/r/noarch",
  "Anaconda-Telemetry-Packages": "defaults/osx-arm64::anaconda-anon-usage-0.4.4-py312hd6b623d_100;pypi/pypi::conda-anaconda-telemetry-0.1.0-pypi_0;defaults/noarch::archspec-0.2.3-pyhd3eb1b0_0;defaults/osx-arm64::boltons-23.0.0-py312hca03da5_0;defaults/osx-arm64::brotli-python-1.0.9-py312h313beb8_7;defaults/osx-arm64::bzip2-1.0.8-h80987f9_5;defaults/osx-arm64::c-ares-1.19.1-h80987f9_0;defaults/osx-arm64::ca-certificates-2024.9.24-hca03da5_0;defaults/osx-arm64::certifi-2024.8.30-py312hca03da5_0;defaults/osx-arm64::cffi-1.16.0-py312h80987f9_0;defaults/noarch::charset-normalizer-2.0.4-pyhd3eb1b0_0;conda-canary/label/dev/osx-arm64::conda-24.9.2+35_g979716cd9-py312_0;defaults/osx-arm64::conda-content-trust-0.2.0-py312hca03da5_0;defaults/noarch::conda-libmamba-solver-24.1.0-pyhd3eb1b0_0;defaults/osx-arm64::conda-package-handling-2.2.0-py312hca03da5_0;defaults/osx-arm64::conda-package-streaming-0.9.0-py312hca03da5_0;defaults/osx-arm64::cryptography-42.0.5-py312hd4332d6_0;defaults/osx-arm64::distro-1.8.0-py312hca03da5_0;defaults/osx-arm64::expat-2.5.0-h313beb8_0;defaults/osx-arm64::fmt-9.1.0-h48ca7d4_0;defaults/osx-arm64::frozendict-2.4.2-py312hca03da5_0;defaults/osx-arm64::icu-73.1-h313beb8_0;defaults/osx-arm64::idna-3.4-py312hca03da5_0;defaults/osx-arm64::jsonpatch-1.33-py312hca03da5_0;defaults/noarch::jsonpointer-2.1-pyhd3eb1b0_0;defaults/osx-arm64::krb5-1.20.1-hf3e1bf2_1;defaults/osx-arm64::libarchive-3.6.2-h62fee54_2;defaults/osx-arm64::libcurl-8.5.0-h3e2b118_0;defaults/osx-arm64::libcxx-14.0.6-h848a8c0_0;defaults/osx-arm64::libedit-3.1.20230828-h80987f9_0;defaults/osx-arm64::libev-4.33-h1a28f6b_1;defaults/osx-arm64::libffi-3.4.4-hca03da5_0;defaults/osx-arm64::libiconv-1.16-h1a28f6b_2;defaults/osx-arm64::libmamba-1.5.8-haeffa04_1;defaults/osx-arm64::libmambapy-1.5.8-py312h1c5506f_1;defaults/osx-arm64::libnghttp2-1.57.0-h62f6fdd_0;defaults/osx-arm64::libsolv-0.7.24-h514c7bf_0;defaults/osx-arm64::libssh2-1.10.0-h02f6b3c_2;defaults/osx-arm64::libxml2-2.10.4-h0dcf63f_1;defaults/osx-arm64::lz4-c-1.9.4-h313beb8_0;defaults/osx-arm64::menuinst-2.0.2-py312hca03da5_0;defaults/osx-arm64::ncurses-6.4-h313beb8_0;defaults/osx-arm64::openssl-3.0.15-h80987f9_0;defaults/osx-arm64::packaging-23.2-py312hca03da5_0;defaults/osx-arm64::pcre2-10.42-hb066dcc_0;defaults/osx-arm64::pip-23.3.1-py312hca03da5_0;defaults/osx-arm64::platformdirs-3.10.0-py312hca03da5_0;defaults/osx-arm64::pluggy-1.0.0-py312hca03da5_1;defaults/noarch::pybind11-abi-4-hd3eb1b0_1;defaults/osx-arm64::pycosat-0.6.6-py312h80987f9_0;defaults/noarch::pycparser-2.21-pyhd3eb1b0_0;defaults/osx-arm64::pysocks-1.7.1-py312hca03da5_0;defaults/osx-arm64::python-3.12.2-h99e199e_0;defaults/osx-arm64::python.app-3-py312h80987f9_0;defaults/osx-arm64::readline-8.2-h1a28f6b_0;defaults/osx-arm64::reproc-14.2.4-hc377ac9_1;defaults/osx-arm64::reproc-cpp-14.2.4-hc377ac9_1;defaults/osx-arm64::requests-2.31.0-py312hca03da5_1;defaults/osx-arm64::ruamel.yaml-0.17.21-py312h80987f9_0;defaults/osx-arm64::setuptools-68.2.2-py312hca03da5_0;defaults/osx-arm64::sqlite-3.41.2-h80987f9_0;defaults/osx-arm64::tk-8.6.12-hb8d0fd4_0;defaults/osx-arm64::tqdm-4.65.0-py312h989b03a_0;defaults/osx-arm64::truststore-0.8.0-py312hca03da5_0;defaults/noarch::tzdata-2024a-h04d1e81_0;defaults/osx-arm64::urllib3-2.1.0-py312hca03da5_1;defaults/osx-arm64::wheel-0.41.2-py312hca03da5_0;defaults/osx-arm64::xz-5.4.6-h80987f9_0;defaults/osx-arm64::yaml-cpp-0.8.0-h313beb8_0;defaults/osx-arm64::zlib-1.2.13-h5a0b063_0;defaults/osx-arm64::zstandard-0.19.0-py312h80987f9_0;defaults/osx-arm64::zstd-1.5.5-hd90d995_0",
  "Anaconda-Telemetry-Search": "conda",
  "Anaconda-Telemetry-Sys-Info": "conda_build_version:n/a;conda_command:search",
  "Anaconda-Telemetry-Virtual-Packages": "archspec.1.m1;conda.24.9.3.dev35.None;osx.14.4.1.None;unix.None.None",
  "if-none-match": "e98c70a0c7edd90df1baccf30a736e03"
}
```

#### Test to ensure install/create terms are being submitted

Test command:

```
conda install conda -v -v -v
```

Expected headers

```json
{
  "User-Agent": "conda/24.9.3.dev35 requests/2.31.0 CPython/3.12.2 Darwin/23.4.0 OSX/14.4.1 solver/libmamba conda-libmamba-solver/24.1.0 libmambapy/1.5.8 aau/0.4.4",
  "Accept-Encoding": "gzip, deflate, br, zstd",
  "Accept": "*/*",
  "Connection": "keep-alive",
  "Anaconda-Telemetry-Channels": "https://repo.anaconda.com/pkgs/main/osx-arm64;https://repo.anaconda.com/pkgs/main/noarch;https://repo.anaconda.com/pkgs/r/osx-arm64;https://repo.anaconda.com/pkgs/r/noarch",
  "Anaconda-Telemetry-Install": "conda",
  "Anaconda-Telemetry-Packages": "defaults/osx-arm64::anaconda-anon-usage-0.4.4-py312hd6b623d_100;pypi/pypi::conda-anaconda-telemetry-0.1.0-pypi_0;defaults/noarch::archspec-0.2.3-pyhd3eb1b0_0;defaults/osx-arm64::boltons-23.0.0-py312hca03da5_0;defaults/osx-arm64::brotli-python-1.0.9-py312h313beb8_7;defaults/osx-arm64::bzip2-1.0.8-h80987f9_5;defaults/osx-arm64::c-ares-1.19.1-h80987f9_0;defaults/osx-arm64::ca-certificates-2024.9.24-hca03da5_0;defaults/osx-arm64::certifi-2024.8.30-py312hca03da5_0;defaults/osx-arm64::cffi-1.16.0-py312h80987f9_0;defaults/noarch::charset-normalizer-2.0.4-pyhd3eb1b0_0;conda-canary/label/dev/osx-arm64::conda-24.9.2+35_g979716cd9-py312_0;defaults/osx-arm64::conda-content-trust-0.2.0-py312hca03da5_0;defaults/noarch::conda-libmamba-solver-24.1.0-pyhd3eb1b0_0;defaults/osx-arm64::conda-package-handling-2.2.0-py312hca03da5_0;defaults/osx-arm64::conda-package-streaming-0.9.0-py312hca03da5_0;defaults/osx-arm64::cryptography-42.0.5-py312hd4332d6_0;defaults/osx-arm64::distro-1.8.0-py312hca03da5_0;defaults/osx-arm64::expat-2.5.0-h313beb8_0;defaults/osx-arm64::fmt-9.1.0-h48ca7d4_0;defaults/osx-arm64::frozendict-2.4.2-py312hca03da5_0;defaults/osx-arm64::icu-73.1-h313beb8_0;defaults/osx-arm64::idna-3.4-py312hca03da5_0;defaults/osx-arm64::jsonpatch-1.33-py312hca03da5_0;defaults/noarch::jsonpointer-2.1-pyhd3eb1b0_0;defaults/osx-arm64::krb5-1.20.1-hf3e1bf2_1;defaults/osx-arm64::libarchive-3.6.2-h62fee54_2;defaults/osx-arm64::libcurl-8.5.0-h3e2b118_0;defaults/osx-arm64::libcxx-14.0.6-h848a8c0_0;defaults/osx-arm64::libedit-3.1.20230828-h80987f9_0;defaults/osx-arm64::libev-4.33-h1a28f6b_1;defaults/osx-arm64::libffi-3.4.4-hca03da5_0;defaults/osx-arm64::libiconv-1.16-h1a28f6b_2;defaults/osx-arm64::libmamba-1.5.8-haeffa04_1;defaults/osx-arm64::libmambapy-1.5.8-py312h1c5506f_1;defaults/osx-arm64::libnghttp2-1.57.0-h62f6fdd_0;defaults/osx-arm64::libsolv-0.7.24-h514c7bf_0;defaults/osx-arm64::libssh2-1.10.0-h02f6b3c_2;defaults/osx-arm64::libxml2-2.10.4-h0dcf63f_1;defaults/osx-arm64::lz4-c-1.9.4-h313beb8_0;defaults/osx-arm64::menuinst-2.0.2-py312hca03da5_0;defaults/osx-arm64::ncurses-6.4-h313beb8_0;defaults/osx-arm64::openssl-3.0.15-h80987f9_0;defaults/osx-arm64::packaging-23.2-py312hca03da5_0;defaults/osx-arm64::pcre2-10.42-hb066dcc_0;defaults/osx-arm64::pip-23.3.1-py312hca03da5_0;defaults/osx-arm64::platformdirs-3.10.0-py312hca03da5_0;defaults/osx-arm64::pluggy-1.0.0-py312hca03da5_1;defaults/noarch::pybind11-abi-4-hd3eb1b0_1;defaults/osx-arm64::pycosat-0.6.6-py312h80987f9_0;defaults/noarch::pycparser-2.21-pyhd3eb1b0_0;defaults/osx-arm64::pysocks-1.7.1-py312hca03da5_0;defaults/osx-arm64::python-3.12.2-h99e199e_0;defaults/osx-arm64::python.app-3-py312h80987f9_0;defaults/osx-arm64::readline-8.2-h1a28f6b_0;defaults/osx-arm64::reproc-14.2.4-hc377ac9_1;defaults/osx-arm64::reproc-cpp-14.2.4-hc377ac9_1;defaults/osx-arm64::requests-2.31.0-py312hca03da5_1;defaults/osx-arm64::ruamel.yaml-0.17.21-py312h80987f9_0;defaults/osx-arm64::setuptools-68.2.2-py312hca03da5_0;defaults/osx-arm64::sqlite-3.41.2-h80987f9_0;defaults/osx-arm64::tk-8.6.12-hb8d0fd4_0;defaults/osx-arm64::tqdm-4.65.0-py312h989b03a_0;defaults/osx-arm64::truststore-0.8.0-py312hca03da5_0;defaults/noarch::tzdata-2024a-h04d1e81_0;defaults/osx-arm64::urllib3-2.1.0-py312hca03da5_1;defaults/osx-arm64::wheel-0.41.2-py312hca03da5_0;defaults/osx-arm64::xz-5.4.6-h80987f9_0;defaults/osx-arm64::yaml-cpp-0.8.0-h313beb8_0;defaults/osx-arm64::zlib-1.2.13-h5a0b063_0;defaults/osx-arm64::zstandard-0.19.0-py312h80987f9_0;defaults/osx-arm64::zstd-1.5.5-hd90d995_0",
  "Anaconda-Telemetry-Sys-Info": "conda_build_version:n/a;conda_command:install",
  "Anaconda-Telemetry-Virtual-Packages": "archspec.1.m1;conda.24.9.3.dev35.None;osx.14.4.1.None;unix.None.None",
  "if-none-match": "e98c70a0c7edd90df1baccf30a736e03"
}
```


#### Test to ensure other commands behave as expected

The delete command will attempt to retrieve repodata and therefore submit telemetry headers.
It won't have any extra headers like the above commands (e.g. `Anaconda-Telemetry-Install` or
`Anaconda-Telemetry-Search`).

Test command:

```
conda remove conda -v -v -v
```

Expected headers

```json
{
  "User-Agent": "conda/24.9.3.dev35 requests/2.31.0 CPython/3.12.2 Darwin/23.4.0 OSX/14.4.1 solver/libmamba conda-libmamba-solver/24.1.0 libmambapy/1.5.8 aau/0.4.4",
  "Accept-Encoding": "gzip, deflate, br, zstd",
  "Accept": "*/*",
  "Connection": "keep-alive",
  "Anaconda-Telemetry-Channels": "https://repo.anaconda.com/pkgs/main/osx-arm64;https://repo.anaconda.com/pkgs/main/noarch;https://repo.anaconda.com/pkgs/r/osx-arm64;https://repo.anaconda.com/pkgs/r/noarch",
  "Anaconda-Telemetry-Packages": "defaults/osx-arm64::anaconda-anon-usage-0.4.4-py312hd6b623d_100;pypi/pypi::conda-anaconda-telemetry-0.1.0-pypi_0;defaults/noarch::archspec-0.2.3-pyhd3eb1b0_0;defaults/osx-arm64::boltons-23.0.0-py312hca03da5_0;defaults/osx-arm64::brotli-python-1.0.9-py312h313beb8_7;defaults/osx-arm64::bzip2-1.0.8-h80987f9_5;defaults/osx-arm64::c-ares-1.19.1-h80987f9_0;defaults/osx-arm64::ca-certificates-2024.9.24-hca03da5_0;defaults/osx-arm64::certifi-2024.8.30-py312hca03da5_0;defaults/osx-arm64::cffi-1.16.0-py312h80987f9_0;defaults/noarch::charset-normalizer-2.0.4-pyhd3eb1b0_0;conda-canary/label/dev/osx-arm64::conda-24.9.2+35_g979716cd9-py312_0;defaults/osx-arm64::conda-content-trust-0.2.0-py312hca03da5_0;defaults/noarch::conda-libmamba-solver-24.1.0-pyhd3eb1b0_0;defaults/osx-arm64::conda-package-handling-2.2.0-py312hca03da5_0;defaults/osx-arm64::conda-package-streaming-0.9.0-py312hca03da5_0;defaults/osx-arm64::cryptography-42.0.5-py312hd4332d6_0;defaults/osx-arm64::distro-1.8.0-py312hca03da5_0;defaults/osx-arm64::expat-2.5.0-h313beb8_0;defaults/osx-arm64::fmt-9.1.0-h48ca7d4_0;defaults/osx-arm64::frozendict-2.4.2-py312hca03da5_0;defaults/osx-arm64::icu-73.1-h313beb8_0;defaults/osx-arm64::idna-3.4-py312hca03da5_0;defaults/osx-arm64::jsonpatch-1.33-py312hca03da5_0;defaults/noarch::jsonpointer-2.1-pyhd3eb1b0_0;defaults/osx-arm64::krb5-1.20.1-hf3e1bf2_1;defaults/osx-arm64::libarchive-3.6.2-h62fee54_2;defaults/osx-arm64::libcurl-8.5.0-h3e2b118_0;defaults/osx-arm64::libcxx-14.0.6-h848a8c0_0;defaults/osx-arm64::libedit-3.1.20230828-h80987f9_0;defaults/osx-arm64::libev-4.33-h1a28f6b_1;defaults/osx-arm64::libffi-3.4.4-hca03da5_0;defaults/osx-arm64::libiconv-1.16-h1a28f6b_2;defaults/osx-arm64::libmamba-1.5.8-haeffa04_1;defaults/osx-arm64::libmambapy-1.5.8-py312h1c5506f_1;defaults/osx-arm64::libnghttp2-1.57.0-h62f6fdd_0;defaults/osx-arm64::libsolv-0.7.24-h514c7bf_0;defaults/osx-arm64::libssh2-1.10.0-h02f6b3c_2;defaults/osx-arm64::libxml2-2.10.4-h0dcf63f_1;defaults/osx-arm64::lz4-c-1.9.4-h313beb8_0;defaults/osx-arm64::menuinst-2.0.2-py312hca03da5_0;defaults/osx-arm64::ncurses-6.4-h313beb8_0;defaults/osx-arm64::openssl-3.0.15-h80987f9_0;defaults/osx-arm64::packaging-23.2-py312hca03da5_0;defaults/osx-arm64::pcre2-10.42-hb066dcc_0;defaults/osx-arm64::pip-23.3.1-py312hca03da5_0;defaults/osx-arm64::platformdirs-3.10.0-py312hca03da5_0;defaults/osx-arm64::pluggy-1.0.0-py312hca03da5_1;defaults/noarch::pybind11-abi-4-hd3eb1b0_1;defaults/osx-arm64::pycosat-0.6.6-py312h80987f9_0;defaults/noarch::pycparser-2.21-pyhd3eb1b0_0;defaults/osx-arm64::pysocks-1.7.1-py312hca03da5_0;defaults/osx-arm64::python-3.12.2-h99e199e_0;defaults/osx-arm64::python.app-3-py312h80987f9_0;defaults/osx-arm64::readline-8.2-h1a28f6b_0;defaults/osx-arm64::reproc-14.2.4-hc377ac9_1;defaults/osx-arm64::reproc-cpp-14.2.4-hc377ac9_1;defaults/osx-arm64::requests-2.31.0-py312hca03da5_1;defaults/osx-arm64::ruamel.yaml-0.17.21-py312h80987f9_0;defaults/osx-arm64::setuptools-68.2.2-py312hca03da5_0;defaults/osx-arm64::sqlite-3.41.2-h80987f9_0;defaults/osx-arm64::tk-8.6.12-hb8d0fd4_0;defaults/osx-arm64::tqdm-4.65.0-py312h989b03a_0;defaults/osx-arm64::truststore-0.8.0-py312hca03da5_0;defaults/noarch::tzdata-2024a-h04d1e81_0;defaults/osx-arm64::urllib3-2.1.0-py312hca03da5_1;defaults/osx-arm64::wheel-0.41.2-py312hca03da5_0;defaults/osx-arm64::xz-5.4.6-h80987f9_0;defaults/osx-arm64::yaml-cpp-0.8.0-h313beb8_0;defaults/osx-arm64::zlib-1.2.13-h5a0b063_0;defaults/osx-arm64::zstandard-0.19.0-py312h80987f9_0;defaults/osx-arm64::zstd-1.5.5-hd90d995_0",
  "Anaconda-Telemetry-Sys-Info": "conda_build_version:n/a;conda_command:remove",
  "Anaconda-Telemetry-Virtual-Packages": "archspec.1.m1;conda.24.9.3.dev35.None;osx.14.4.1.None;unix.None.None",
  "if-none-match": "e98c70a0c7edd90df1baccf30a736e03"
}
```
