#!/bin/bash

# Used to switch CONDA_EXE to the one located in development environment
# To use this script, run `source develop.sh`

if ! (return 0 2> /dev/null); then
    echo "ERROR: Source this script: source '$0'." >&2
    exit 1
fi

CONDA_ENV_DIR="./env"

conda create -p "$CONDA_ENV_DIR" --file tests/requirements.txt --file tests/requirements-ci.txt --yes
conda activate "$CONDA_ENV_DIR"
pip install -e .

CONDA_EXE="$CONDA_PREFIX/condabin/conda"
