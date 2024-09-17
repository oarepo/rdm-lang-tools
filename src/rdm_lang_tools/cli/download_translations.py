#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
from collections import defaultdict
from pathlib import Path

import click
import polib

from rdm_lang_tools.cli.check_duplicates import get_translation_files
from rdm_lang_tools.repository import get_repository


@click.command()
@click.option(
    "--output-directory",
    "-o",
    help="Target directory for writing the report",
    default=Path.cwd() / "translations",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
)
@click.option(
    "--temp-directory",
    "-t",
    help="Path to the directory where temporary files will be stored",
    type=click.Path(),
    default=Path.cwd() / ".temp",
)
@click.argument("repository", type=click.Path(exists=True, file_okay=False))
@click.argument("language")
def main(*, repository, language, output_directory, temp_directory):
    """
    Check for duplicate packages in the repository
    and generate a report for each of the specified languages.
    """
    repository = get_repository(repository, temp_directory)

    if not output_directory.exists():
        output_directory.mkdir(parents=True)
    #
    # repository.download_invenio_packages()
    # repository.download_translations()

    translations = repository.local_invenio_packages_with_translations()

    entries = defaultdict(list)
    for pkg, local_path, translation_path in translations:
        translation_files = get_translation_files(local_path, translation_path)
        if language not in translation_files:
            print(f"Language not in package {pkg} at {local_path}, skipping")
            continue
        # read and store the items
        po_file = translation_files[language]
        po = polib.pofile(po_file.read_text())
        for entry in po:
            entries[entry.msgid].append((entry, f"{pkg}:{translation_path}"))

    # generate the target po file
    target_po = polib.POFile()
    for msgid, items in entries.items():
        if len(items) == 1:
            target_po.append(items[0][0])
            continue

        translations = defaultdict(list)
        for item, path in items:
            translations[item.msgstr].append((item, path))

        occurrences = []
        translation_comments = []
        comments = []
        for item, path in items:
            occurrences.extend(item.occurrences)
            translation_comments.extend(item.tcomment)
            comments.extend(item.comment)

        for msgstr, items in translations.items():
            translation_comments.append(
                f"Translations: {msgstr} in {', '.join(path for _, path in items)}"
            )

        item = items[0][0]
        item.occurrences = occurrences
        item.tcomment = "; ".join(translation_comments)
        item.comment = "; ".join(comments)

        if len(translations) > 1:
            item.fuzzy = True
        target_po.append(item)

    language_directory = output_directory / language
    language_directory.mkdir(parents=True, exist_ok=True)
    target_po.save(language_directory / f"{language}.po")


if __name__ == "__main__":
    main()
