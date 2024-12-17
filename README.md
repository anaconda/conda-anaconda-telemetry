# Conda Anaconda Telemetry

Welcome to the Conda Anaconda Telemetry project! This project is a plugin that
submits data about conda's usage to Anaconda. This helps Anaconda learn more about
those using conda. This plugin is also an example of how others can leverage conda's
plugin system to begin collecting more information about their conda users too.

## Installation

To begin using this plugin, install it in your base environment with the following command:

```commandline
conda install --name base conda-anaconda-telemetry
```

## Disabling

To disable this plugin, you can either add the following to your `.condarc` file:

```yaml
plugins:
  anaconda_telemetry: false
```

Or remove it from your base environment:

```commandline
conda remove --name base conda-anaconda-telemetry
```

## Contributing to this repository

Contributions are very welcome 😄

Feel free to:
1. File bug reports
2. Create feature requests
3. Open pull requests to resolve issues available in the [Github issues queue](https://github.com/anaconda/conda-anaconda-telemetry/issues).
4. Review open pull requests
5. Report any typos, wrong/outdated information on the [documentation website](https://anaconda.github.io/conda-anaconda-telemetry/).
6. Engage in ongoing discussions in this project and add new ideas.
