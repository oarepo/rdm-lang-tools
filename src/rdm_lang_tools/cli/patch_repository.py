#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import json
import shutil
from pathlib import Path

import click
import polib

from rdm_lang_tools.cli.check_duplicates import get_translation_files
from rdm_lang_tools.repository import get_repository


@click.command()
@click.option(
    "--temp-directory",
    "-t",
    help="Path to the directory where temporary files will be stored",
    type=click.Path(),
    default=Path.cwd() / ".temp",
)
@click.argument("repository", type=click.Path(exists=True, file_okay=False))
@click.argument("language")
@click.option("--skip-download", default=False, is_flag=True)
@click.option("--skip-download-repository", default=False, is_flag=True)
@click.option("--skip-download-translations", default=False, is_flag=True)
def main(
    *,
    repository,
    language,
    temp_directory,
    skip_download,
    skip_download_repository,
    skip_download_translations
):
    """
    Download translations and patch the repository with the downloaded translations.
    """
    if not temp_directory.exists():
        skip_download_repository = False
        skip_download_translations = False

    repository = get_repository(repository, temp_directory)

    if skip_download:
        skip_download_repository = True
        skip_download_translations = True

    if not skip_download_repository:
        repository.download_invenio_packages()

    if not skip_download_translations:
        repository.download_translations()

    translations = repository.local_invenio_packages_with_translations()

    fix_rdm_package(translations, language)

    for pkg, local_path, translation_path in translations:
        translation_path = translation_path.replace('invenio-rdm-records', 'invenio_rdm_records')
        translation_files = get_translation_files(local_path, translation_path)
        if language not in translation_files:
            print(f"Language not in package {pkg} at {local_path}, skipping")
            continue
        po_file = translation_files[language]
        if "invenio-rdm-records" in str(po_file):
            po_file = local_path / (
                str(po_file.relative_to(local_path)).replace("invenio-rdm-records", "invenio_rdm_records")
            )

        # check if there is a json file and if yes, fix it
        json_file = po_file.parent / "translations.json"
        po = polib.pofile(po_file.read_text())

        if json_file.exists():
            # read the json file
            translations = json.loads(json_file.read_text())
            # read the po file
            po = polib.pofile(po_file.read_text())
            for entry in po:
                translations[entry.msgid] = entry.msgstr
            # write the json file back
            json_file.write_text(json.dumps(translations, indent=2, ensure_ascii=False))
            file_to_copy = json_file
        else:
            # compile to .mo
            po.save_as_mofile(po_file.with_suffix(".mo"))
            file_to_copy = po_file.with_suffix(".mo")

        for f in (file_to_copy, po_file):
            print("Copying file", f)
            relative_file_to_copy = f.relative_to(local_path)
            target_file = repository.get_site_packages_dir() / relative_file_to_copy
            print("    -> ", target_file)
            if not target_file.exists():
                print(f"      Warning: File {target_file} does not exist")
            if not target_file.parent.exists():
                target_file.parent.mkdir(parents=True)
            shutil.copy(f, target_file)

    # copy those to the repository

def fix_rdm_package(translations, language):
    for pkg, local_path, translation_path in translations:
        if pkg != 'invenio-rdm-records':
            continue
        if not translation_path.startswith('invenio-rdm-records/'):
            continue
        # copy the content of the translation path to invenio_rdm_records
        translation_path = translation_path.replace('<lang>', language)

        shutil.copy(
            Path(local_path) / translation_path,
            Path(local_path) / translation_path.replace('invenio-rdm-records', 'invenio_rdm_records')
        )

if __name__ == "__main__":
    main()
