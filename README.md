# SAE cleaning-status-filter

This component is part of the Starwit Awareness Engine (SAE). See umbrella repo here: https://github.com/starwit/starwit-awareness-engine

## How to set up
- Make sure you have Poetry installed (pipx is recommended: https://python-poetry.org/docs/#installing-with-pipx)
- Run `poetry install`

## How to Build

See [dev readme](doc/DEV_README.md) for build instructions.

## Model Development
In order to detect the mirror a trained model is necessary. See [model development](doc/Model_Development.md) documentation for more details.

## Github Workflows and Versioning

The following Github Actions are available:

* [PR build](.github/workflows/pr-build.yml): Builds python project for each pull request to main branch. `poetry install` and `poetry run pytest` are executed, to compile and test python code.
* [Build and publish latest image](.github/workflows/build-publish-latest.yml): Manually executed action. Same like PR build. Additionally puts latest docker image to internal docker registry.
* [Create release](.github/workflows/create-release.yml): Manually executed action. Creates a github release with tag, docker image in internal docker registry, helm chart in chartmuseum by using and incrementing the version in pyproject.toml. Poetry is updating to next version by using "patch, minor and major" keywords. If you want to change to non-incremental version, set version in directly in pyproject.toml and execute create release afterwards.