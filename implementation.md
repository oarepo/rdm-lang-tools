# Implementation details

## Collecting translations (common for all commands)

All commands take a path to the Invenio RDM repository as the first argument.
Then they:

1. run `pip list --format=json` to get the list of installed packages and their versions
2. select all packages with name starting with `invenio-`
3. for each package:
   1. clone its github repository to a temporary directory (`.temp` by default) and checkout 
      tag `v<package-version>`
      * implementation in [Repository.download_invenio_packages](./blob/main/src/rdm_lang_tools/repository.py#L39)
   2. run `tx pull -a` to download translations from transifex. This creates
      `.po` files for each resource in the transifex (that is, both the python
      and the javascript translations are downloaded as `.po` files)
      * implementation in [Repository.download_translations](./blob/main/src/rdm_lang_tools/repository.py#L61)
   3. parse `.tx/config` and get the paths where the `.po` files have been downloaded
      * implementation in [Repository.local_invenio_packages_with_translations](./blob/main/src/rdm_lang_tools/repository.py#L123)

## Merging the translations

The `download-translations` command merges the translations into a single `.po` file.
It takes the paths to the downloaded translations and:

1. reads all `.po` files, and filling dict of msgid -> List[POEntry]
2. for each msgid, it:
   1. if there is only one translation, it adds it to the output file
   2. if there are multiple different translations for a single msgid, 
      it adds the first one, marking it as fuzzy and adding a translator 
      comment with the list of all the different translations and in which
      transifex resource they were found

## Splitting and uploading translations

The `split-and-upload-translations` takes the file created in the previous step
and for each of the original `.po` file, it updates its msgids with the translation.
Then it prints the path to the file and lets the user upload the file to transifex.

## Patching the repository

For each of the downloaded transifex resources (as `.po` files) inside the temp directory, 
the `patch-repository` command does:

1. reads the `.po` file
2. saves it as `.mo` file for babel
3. if there is a `translations.json` file present in the same directory, 
   it overwrites the translations inside the file.
4. For the `po`, `mo` and `json` files, it locates the file inside the
   RDM repository venv and overwrites the original file with the new version.

After patching, user should invoke `invenio webpack buildall` to rebuild the UI.