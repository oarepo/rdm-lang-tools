# Tools for developing RDM translations

This repository contains tools for developing translations for the InvenioRDM project.
If you just want to see the results of the latest run, head to the [reports](reports) directory.

## Installation

To install locally

```bash
uv venv               # or python3.12 -m venv .venv
uv pip install -e .   # or .venv/bin/pip install -e .
```

## Usage

### Checking if there are more than one translations for a single key

```bash
check-duplicates <path-to-invenio-rdm>
```

This command will download invenio packages locally to `.temp` directory,
then pull translations from transifex and check if there are more translations for a single key.
Downloading the packages and translations can take a while, so be patient.

Note: you need to have git and transifex set up on your machine for the command to work.

### Downloading all translations and merging them into a single .po file

```bash
download-translations <path-to-invenio-rdm> <language> --output-directory=./translations
```

This command will download invenio packages locally to `.temp` directory,
then pull translations from transifex and merge them into a single .po file
ready to be translated.

Translate the po file in a tool like poedit or directly inside pycharm/code with github copilot
plugin to help you.

### Splitting and uploading translations

Translations from the previous step can be split back into original
files and uploaded to transifex via:

```bash
split-and-upload-translations <path-to-invenio-rdm> <po_file> <language>
```

This command will split the translations into original files (downloaded inside the .temp directory).
Then, for each file, it will print path to the file and let you upload the file yourself (it seems
that transifex push does not work for me for some reason, commented out in sources if you want to try it) 
so you'll need to upload the file manually from transifex web interface.

### Checking translations with chatgpt

The following command will download the translations from transifex and output chatgpt prompts.

```bash
check-via-chatgpt <path-to-invenio-rdm> <language> <language_as_english_text> <output_file.html>

# For example:
check-via-chatgpt ../rdm13 cs czech gpt_script.html
```

Open the generated html in browser and follow the instructions.

### Checking translations in a running repository

To download the newest translations and apply them to an installed RDM repository, call

```bash
patch-repository <path-to-invenio-rdm> <language>
```

Then build the repository UI and check if the translations are correct.

