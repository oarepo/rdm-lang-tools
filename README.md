# Tools for developing RDM translations

This repository contains tools for developing translations for the InvenioRDM project.
If you just want to see the results of the latest run, head to the [reports](reports) directory.

## Installation

To install locally

```bash
uv venv
uv pip install -e .
```

## Usage

### Checking if there are more translations for a single key

```bash
check-duplicates <path-to-invenio-rdm>
```

This command will download invenio packages locally to `.temp` directory,
then pull translations from transifex and check if there are more translations for a single key.
Downloading the packages and translations can take a while, so be patient.

Note: you need to have git and transifex set up on your machine for the command to work.