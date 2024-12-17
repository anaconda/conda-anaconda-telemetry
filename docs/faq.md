# FAQ

## What happens when I enable conda-anaconda-telemetry?

When the `conda-anaconda-telemetry` plugin is installed and enabled, the plugin will collect additional
information about how conda is being used. This is then submitted to the channel servers that
are currently configured via HTTP request headers. This allows channel owners to gain additional
insights about how their channels are being used.

## What data is tracked by this plugin?

We currently collect the following information when this plugin is installed:

- Installed [virtual packages](https://docs.conda.io/projects/conda/en/stable/dev-guide/plugins/virtual_packages.html)
  (e.g., `glibc` version or your current architecture specifications, such as `m1`)
- Installed packages in the active environment (e.g. the output of `conda list`)
- Configured channels (e.g. `defaults` or `conda-forge`)
- System information (e.g. `conda-build` version or the command currently being run)
- When `conda search` is run, we track the packages that are being searched for
- When `conda install` or `conda create` is run, we track the packages that are being installed that are
  specified at the command line (e.g. for the command `conda install package-a package-b`, `package-a` and
  `package-b` will be tracked)

## Which commands are you tracking?

We only track commands that make network requests. This includes the following:

- `conda search`
- `conda install`
- `conda update`
- `conda create`
- `conda remove`
- `conda notices`
