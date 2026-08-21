#!/usr/bin/env bash
# scripts/benchmark_timing.sh
#
# Measure the overhead of conda-anaconda-telemetry by comparing command
# wall-clock time with telemetry enabled vs disabled, for each of:
# env create, package install, search, and the error path.
#
# Prerequisites:
#   - hyperfine is on PATH
#   - conda-anaconda-telemetry is installed in the active conda base.
#
# The install benchmarks use a scratch env at /tmp/cat-bench.
#
# Usage:
#   bash scripts/benchmark_timing.sh [--output-table] [--only=create,install,search,error] [-n=25]
#
# --output-table also prints one combined markdown table summary, example:
#    | Benchmark  | Disabled (s)  | Enabled (s)   | Overhead |
#    |:---------|:------------|:------------|:-------|
#    | create     | 5.148 ± 0.414 | 5.033 ± 0.235 | -2.2%    |
#    | install    | 4.169 ± 1.085 | 4.109 ± 1.098 | -1.4%    |
#    | search     | 2.183 ± 0.105 | 2.210 ± 0.234 | +1.2%    |
#    | error path | 4.326 ± 0.637 | 4.877 ± 0.587 | +12.7%   |
#
# --only restricts which benchmarks run (default: all, comma-separated).
# -n sets the number of hyperfine runs per benchmark (default: 25).
#

set -euo pipefail

ALL_BENCHMARKS=(create install search error)
# Benchmarks that leave state in $BENCH_PREFIX and must be cleaned up after.
CLEANUP_BENCHMARKS=(create install error)

is_known_benchmark() {
  local name="$1" candidate
  for candidate in "${ALL_BENCHMARKS[@]}"; do
    [[ "$candidate" == "$name" ]] && return 0
  done
  return 1
}

needs_cleanup() {
  local name="$1" candidate
  for candidate in "${CLEANUP_BENCHMARKS[@]}"; do
    [[ "$candidate" == "$name" ]] && return 0
  done
  return 1
}

OUTPUT_TABLE=false
SELECTED=("${ALL_BENCHMARKS[@]}")
RUNS=25
for arg in "$@"; do
  case "$arg" in
    --output-table) OUTPUT_TABLE=true ;;
    --only=*)
      IFS=',' read -ra SELECTED <<< "${arg#--only=}"
      for name in "${SELECTED[@]}"; do
        if ! is_known_benchmark "$name"; then
          echo "Unknown benchmark: ${name} (valid: ${ALL_BENCHMARKS[*]})" >&2
          exit 1
        fi
      done
      ;;
    -n=*)
      RUNS="${arg#-n=}"
      if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
        echo "-n must be a positive integer, got: ${RUNS}" >&2
        exit 1
      fi
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

WARMUP=2
DISABLED="CONDA_PLUGINS_ANACONDA_TELEMETRY=false"
BENCH_PREFIX="/tmp/cat-bench"

# hyperfine runs each benchmarked command in a fresh, non-login shell, which
# does not source conda's shell hook - without it, `conda` resolves to the
# bare binary and channel config (condarc.d discovery) is incomplete,
# causing spurious NoChannelsConfiguredError failures. Source the hook and
# activate cat's base env in every benchmarked command and --prepare step.
CONDA_INIT="source \"$HOME/miniconda3/etc/profile.d/conda.sh\" && conda activate base &&"

JSON_DIR=$(mktemp -d)
trap 'rm -rf "$JSON_DIR"' EXIT

# run_benchmark <name> <label> <prepare_cmd> <disabled_cmd> <enabled_cmd>
# prepare_cmd may be the empty string to skip --prepare.
run_benchmark() {
  local name="$1" label="$2" prepare="$3" disabled_cmd="$4" enabled_cmd="$5"
  echo ""
  echo ">>> ${label}"
  if [ -n "$prepare" ]; then
    hyperfine \
      --shell bash \
      --runs "$RUNS" \
      --warmup "$WARMUP" \
      --prepare "$prepare" \
      --export-json "${JSON_DIR}/${name}.json" \
      "$disabled_cmd" \
      "$enabled_cmd"
  else
    hyperfine \
      --shell bash \
      --runs "$RUNS" \
      --warmup "$WARMUP" \
      --export-json "${JSON_DIR}/${name}.json" \
      "$disabled_cmd" \
      "$enabled_cmd"
  fi
}

run_create() {
  run_benchmark create \
    "conda create -p ${BENCH_PREFIX} python -y" \
    "${CONDA_INIT} conda env remove -p ${BENCH_PREFIX} -q -y 2>/dev/null || true" \
    "${CONDA_INIT} ${DISABLED} conda create -p ${BENCH_PREFIX} python -y" \
    "${CONDA_INIT} conda create -p ${BENCH_PREFIX} python -y"
}

run_install() {
  # prepare pre-installs numpy so each timed run measures a reinstall.
  run_benchmark install \
    "conda install -p ${BENCH_PREFIX} numpy -y" \
    "${CONDA_INIT} conda install -p ${BENCH_PREFIX} numpy -y -q 2>/dev/null || true" \
    "${CONDA_INIT} ${DISABLED} conda install -p ${BENCH_PREFIX} numpy -y" \
    "${CONDA_INIT} conda install -p ${BENCH_PREFIX} numpy -y"
}

run_search() {
  run_benchmark search \
    "conda search scikit-learn" \
    "" \
    "${CONDA_INIT} ${DISABLED} conda search scikit-learn" \
    "${CONDA_INIT} conda search scikit-learn"
}

run_error() {
  run_benchmark error \
    "conda install -p ${BENCH_PREFIX} nonexistent-packageabc (error path)" \
    "" \
    "${CONDA_INIT} ${DISABLED} conda install -p ${BENCH_PREFIX} nonexistent-packageabc 2>/dev/null; true" \
    "${CONDA_INIT} conda install -p ${BENCH_PREFIX} nonexistent-packageabc 2>/dev/null; true"
}

echo "================================================================"
echo "conda-anaconda-telemetry OTel benchmark (${RUNS} runs each)"
echo "================================================================"

SUMMARIZE_ARGS=()
NEEDS_ENV_CLEANUP=false
for name in "${SELECTED[@]}"; do
  case "$name" in
    create) run_create; SUMMARIZE_ARGS+=("create=${JSON_DIR}/create.json") ;;
    install) run_install; SUMMARIZE_ARGS+=("install=${JSON_DIR}/install.json") ;;
    search) run_search; SUMMARIZE_ARGS+=("search=${JSON_DIR}/search.json") ;;
    error) run_error; SUMMARIZE_ARGS+=("error path=${JSON_DIR}/error.json") ;;
  esac
  if needs_cleanup "$name"; then
    NEEDS_ENV_CLEANUP=true
  fi
done

if [ "$NEEDS_ENV_CLEANUP" = true ]; then
  conda env remove -p "${BENCH_PREFIX}" -q -y > /dev/null 2>&1 || true
fi

if [ "$OUTPUT_TABLE" = true ]; then
  echo -e "=======================Summary==============================\n"
  python "$(dirname "$0")/_summarize_benchmarks.py" "${SUMMARIZE_ARGS[@]}"
fi
