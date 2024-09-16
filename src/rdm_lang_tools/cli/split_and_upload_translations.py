import shutil
import sys
from collections import defaultdict
from pathlib import Path
from pprint import pprint
from subprocess import CalledProcessError, check_call

import polib

import click

from rdm_lang_tools.cli.check_duplicates import get_translation_files
from rdm_lang_tools.repository import get_repository


@click.command()
@click.argument("repository", type=click.Path(exists=True, file_okay=False))
@click.argument("input_po_file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("language")
@click.option(
    "--temp-directory",
    "-t",
    help="Path to the directory where temporary files will be stored",
    type=click.Path(),
    default=Path.cwd() / ".temp",
)
def main(*, repository, input_po_file, language, temp_directory):
    """
    Check for duplicate packages in the repository
    and generate a report for each of the specified languages.
    """
    repository = get_repository(repository, temp_directory)

    global_translations = polib.pofile(Path(input_po_file).read_text())
    global_translations_by_msgid = {
        x.msgid: x.msgstr for x in global_translations
    }

    translations = repository.local_invenio_packages_with_translations()

    for pkg, local_path, translation_path in translations:
        translation_files = get_translation_files(local_path, translation_path)
        if language not in translation_files:
            print(f"Language not in package {pkg} at {local_path}, skipping")
            continue
        # read and store the items
        po_file = translation_files[language]
        po = polib.pofile(po_file.read_text())
        modified = False
        for entry in po:
            if entry.msgid not in global_translations_by_msgid:
                print(f"Missing msgid {entry.msgid} in global translations")
                continue
            global_translation = global_translations_by_msgid[entry.msgid]
            if global_translation != entry.msgstr:
                print(f"Translation mismatch for {entry.msgid} in {pkg}:{translation_path}")
                print(f"Global translation: >{global_translation}<")
                print(f"Local translation: >{entry.msgstr}<")
                entry.msgstr = global_translation
                modified = True
        if modified:
            # save the backup of the pofile
            shutil.copy(po_file, po_file.with_suffix(".po.bak"))

            # save the pofile
            print("Saved the modified pofile", po_file)
            po.save(po_file)

            # call the tx push command
            print(f"Calling tx push -t -l {language} inside {po_file.parent}")
            # try:
            #     check_call(
            #         ["tx", "push", "-t", "-l", language],
            #         cwd=po_file.parent,
            #     )
            # except CalledProcessError:
            #     print(f"Failed to push translations for {pkg}", file=sys.stderr)

            sys.exit(1)


if __name__ == "__main__":
    main()
