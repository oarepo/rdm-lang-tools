#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from random import shuffle

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
@click.argument("language_english_word")
@click.argument("output-file", type=click.Path(), default="gpt_script.html")
@click.option("--skip-download", default=False, is_flag=True)
def main(
    *,
    repository,
    language,
    temp_directory,
    language_english_word,
    skip_download,
    output_file,
):
    """
    Check for duplicate packages in the repository
    and generate a report for each of the specified languages.
    """
    repository = get_repository(repository, temp_directory)

    if not skip_download:
        repository.download_invenio_packages()
        repository.download_translations()

    translations = repository.local_invenio_packages_with_translations()

    entries = defaultdict(set)
    for pkg, local_path, translation_path in translations:
        translation_files = get_translation_files(local_path, translation_path)
        if language not in translation_files:
            print(f"Language not in package {pkg} at {local_path}, skipping")
            continue
        # read and store the items
        po_file = translation_files[language]
        po = polib.pofile(po_file.read_text())
        for entry in po:
            entries[entry.msgid].add(entry.msgstr)

    list_entries = list(entries.items())
    shuffle(list_entries)

    out_html = [
        "<html><head><meta charset='UTF-8'>",
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/clipboard.js/2.0.11/clipboard.min.js"></script>',
        "</head><body>",
        "Click on the button to copy chunk to clipboard, then paste it to chatgpt, model GPT-4o.",
        "Enter 'next' to get the next suggestion from chatgpt.<br><br>",
    ]

    idx = 0
    while len(list_entries):
        idx += 1
        word_count = 0
        to_process = []
        while word_count < 1000 and list_entries:
            msgid, msgstrs = list_entries.pop()
            msgstrs = "; ".join(msgstrs)
            if not msgstrs:
                continue
            to_process.append(f"{msgid}")
            to_process.append(f"{msgstrs}")
            to_process.append("")
            # split on word boundaries
            word_count += (
                2 + len(re.split(r"\s+", msgid)) + len(re.split(r"\s+", msgstrs))
            )

        val = (
            f"Check if the following {language_english_word} "
            f"translations (first line is English, second "
            f"{language_english_word}, separated by newline) "
            f"are terminologically consistent "
            "and return the first inconsistency found."
            "\n" + "\n".join(to_process)
        )
        val = escape(val)
        out_html.append(
            f"<button class='btn' data-clipboard-target='#copy-{idx}'>Copy chunk #{idx} to clipboard</button>"
        )
        out_html.append(f"<input type='hidden' id='copy-{idx}' value='{val}'>")

    out_html.append("</body><script>new ClipboardJS('.btn');</script></html>")

    with open(output_file, "w") as f:
        f.write("\n".join(out_html))


if __name__ == "__main__":
    main()
