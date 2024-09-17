#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import dataclasses
import datetime
import shutil
from collections import defaultdict, namedtuple
from pathlib import Path
from typing import Dict, List

import click
import jinja2
import polib

from rdm_lang_tools.repository import get_repository


def get_translation_files(local_path, translation_path):
    # find <lang> in translation path and split the dir there
    translation_dir = local_path / translation_path.split("<lang>")[0]
    # find all files in the lang directory
    langs = [x.name for x in translation_dir.glob("*") if x.is_dir()]
    ret = {}
    for lang in langs:
        ret[lang] = local_path / translation_path.replace("<lang>", lang)
    return ret


TRR = namedtuple("TRR", ["key", "value", "package", "file"])


@dataclasses.dataclass
class TranslationRegistry:
    by_key: Dict[str, List[TRR]] = dataclasses.field(
        default_factory=lambda: defaultdict(list)
    )
    by_value: Dict[str, List[TRR]] = dataclasses.field(
        default_factory=lambda: defaultdict(list)
    )

    def add(self, key, value, package, file):
        if not value or not value.strip():
            return
        trr = TRR(key, value, package, file)
        self.by_key[key].append(trr)
        self.by_value[value].append(trr)

    def load(self, package, translation_file: Path, relative_path):
        if translation_file.suffix != ".po":
            print(
                f"Can not handle translation with extension {translation_file.suffix}"
            )
            return

        po = polib.pofile(translation_file.read_text())
        for entry in po:
            self.add(entry.msgid, entry.msgstr, package, relative_path)

    def get_unclear_values(self):
        ret = {}
        for key, trrs in self.by_key.items():
            if len(trrs) == 1:
                continue
            values = set(x.value for x in trrs)
            if len(values) > 1:
                ret[key] = list(sorted(trrs, key=lambda x: x.value))
        return ret

    def get_values_with_multiple_keys(self):
        ret = {}
        for value, trrs in self.by_value.items():
            if len(trrs) == 1:
                continue
            keys = set(x.key for x in trrs)
            if len(keys) > 1:
                ret[value] = list(sorted(trrs, key=lambda x: x.key))
        return ret


def generate_multiple_keys_protocol(target_directory, lang, registry):
    values_with_multiple_keys_report_file = target_directory / f"{lang}.md"

    values_with_multiple_keys = registry.get_values_with_multiple_keys()

    if not values_with_multiple_keys:
        return

    jinja_env = get_jinja_env()

    template = jinja_env.get_template("multiple_keys_report.md.jinja2")
    with open(values_with_multiple_keys_report_file, "w") as f:
        f.write(
            template.render(
                lang=lang,
                date=str(datetime.date.today()),
                values_with_multiple_keys=values_with_multiple_keys,
            )
        )


def generate_inconsistent_translations_protocol(target_directory, lang, registry):
    duplicates_report_file = target_directory / f"{lang}.md"
    unclear_values = registry.get_unclear_values()
    if not unclear_values:
        return
    jinja_env = get_jinja_env()
    template = jinja_env.get_template("inconsistent_translations_report.md.jinja2")
    with open(duplicates_report_file, "w") as f:
        f.write(
            template.render(
                lang=lang,
                date=str(datetime.date.today()),
                unclear_values=unclear_values,
            )
        )


def get_jinja_env():
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent.parent / "templates"),
        autoescape=False,
    )

    def show_whitespaces(value):
        return value.replace("\n", "↵ ")

    jinja_env.filters["whitespaces"] = show_whitespaces
    return jinja_env


def check_duplicates(target_directory, temp_directory, repository, languages):
    repository.download_invenio_packages()
    repository.download_translations()
    translations = repository.local_invenio_packages_with_translations()
    registry_by_language = defaultdict(TranslationRegistry)
    for pkg, local_path, translation_path in translations:
        translation_files = get_translation_files(local_path, translation_path)
        for lang, translation_file in translation_files.items():
            registry_by_language[lang].load(
                pkg, translation_file, translation_file.relative_to(local_path)
            )

    multiple_keys_protocol_directory = target_directory / "multiple_keys"
    inconsistent_translations_protocol_directory = (
        target_directory / "inconsistent_translations"
    )

    if multiple_keys_protocol_directory.exists():
        shutil.rmtree(multiple_keys_protocol_directory)
    multiple_keys_protocol_directory.mkdir(parents=True)

    if inconsistent_translations_protocol_directory.exists():
        shutil.rmtree(inconsistent_translations_protocol_directory)
    inconsistent_translations_protocol_directory.mkdir(parents=True)

    for lang, registry in registry_by_language.items():
        generate_multiple_keys_protocol(
            multiple_keys_protocol_directory, lang, registry
        )
        generate_inconsistent_translations_protocol(
            inconsistent_translations_protocol_directory, lang, registry
        )


@click.command()
@click.option(
    "languages", "-l", multiple=True, help="Languages to check for duplicates"
)
@click.option(
    "--output-directory",
    "-o",
    help="Target directory for writing the report",
    default=Path.cwd() / "reports",
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
def main(*, repository, languages, output_directory, temp_directory):
    """
    Check for duplicate packages in the repository
    and generate a report for each of the specified languages.
    """
    repository = get_repository(repository, temp_directory)

    if not output_directory.exists():
        output_directory.mkdir(parents=True)

    check_duplicates(output_directory, temp_directory, repository, languages)


if __name__ == "__main__":
    main()
