# conda-anaconda-telemetry

Anaconda Telemetry for conda

## Development

To begin developing for this project, source the `develop.sh` script (macOS and Linux only).
Run the following command from the root of your project directory.

```bash
source develop.sh
```

This will create a new environment in the `./env` folder of your project and modifies
`CONDA_EXE` to point to an isolated version of conda within this environment.

To update this environment when new dependencies are added to `requirements.txt`, you
can run the same `source develop.sh` command as above.

### Setting up OTEL collector and Elastic Search

This project comes with a `docker-compose.yaml` file which can be used to start
a locally running instance of ElasticSearch and an OTEL collector container that
will submit data to ElasticSearch. To initialize this, you first need to copy
the `env-template` file to the location `.env` with the following command:

```bash
cp env-template .env
```

This `.env` file contains  sensitive information such as passwords and encryption keys.
Please update these environment variables as needed.
