import json
import os
import shutil
import subprocess
from pathlib import Path

import click
import yaml
import requests

from rdm_lang_tools.repository import get_repository, Repository

log_stream = None

@click.command("apply-patches")
@click.argument("repository", type=click.Path(exists=True, file_okay=False))
@click.argument("patch_definitions", type=click.Path(exists=True, file_okay=True))
@click.option("--download-translations", is_flag=True)
@click.option("--temp-directory", type=click.Path(), default=None)
@click.option('--single-package')
@click.option('--from', 'from_package', default=None, type=int, help="The package # to start from")
def apply_patches(repository, patch_definitions, download_translations, temp_directory, single_package=None, from_package=None):
    """Apply a patch to an Invenio repository."""
    global log_stream

    click.echo(f"Patching {repository} using {patch_definitions}")

    temp_directory = temp_directory or Path.cwd() / ".temp"
    temp_directory.mkdir(exist_ok=True)

    log_file = temp_directory / "apply-patches.log"
    log_stream = log_file.open("w")

    repository = get_repository(repository, temp_directory)

    with Path(patch_definitions).open() as f:
        patches = yaml.safe_load(f.read())

    package_versions = {
        x['name']: x['version'] for x in repository.installed_packages
    }

    idx = 0
    for pkg, definition in patches.items():
        idx += 1
        if single_package and single_package != pkg:
            continue
        if from_package and idx < from_package:
            continue
        print("Applying patch", idx, "of", len(patches))
        apply_patch(repository, pkg, definition, package_versions[pkg], download_translations)

def run_command(*args, **kwargs):
    env = {
        **os.environ,
    }
    env.pop('VIRTUAL_ENV', None)
    print("Running command", args, file=log_stream)
    result = subprocess.run(*args, env=env, capture_output=True, **kwargs)
    print("STDOUT", file=log_stream)
    print(result.stdout.decode('utf-8'), file=log_stream)
    print("STDERR", file=log_stream)
    print(result.stderr.decode('utf-8'), file=log_stream)
    print(file=log_stream)

    if result.returncode != 0:
        click.secho(f"Command failed {args}")
        click.secho("STDOUT")
        click.secho(result.stdout.decode('utf-8'))
        click.secho("STDERR")
        click.secho(result.stderr.decode('utf-8'))
        raise subprocess.CalledProcessError(result.returncode, args)

def apply_patch(repository: Repository, package_name, definition, package_version, download_translations):
    click.secho(f"    Applying patch to {package_name} @ {package_version}", fg="green")
    package_path = repository.local_package_path(package_name)
    if package_path.exists():
        shutil.rmtree(package_path)

    click.secho(f"      Downloading package")
    repository.download_package("https://github.com/inveniosoftware/" + package_name,
                                package_version, package_path, log_stream)
    for pull_request in definition.get('pull-requests', []):
        if pull_request.endswith("/files"):
            pull_request = pull_request[:-6]
        if pull_request.endswith("/"):
            pull_request = pull_request[:-1]

        click.secho(f"      Applying pull request {pull_request}")
        patch_data = requests.get(f"{pull_request}.diff").content

        # Apply the patch
        run_command(["git", "apply", "-"],
                        input=patch_data, cwd=package_path)


    if not (package_path / ".tx").exists():
        click.secho(f"      No translations support found in package, skipping", fg="yellow")
        return

    click.secho(f"      Looking for javascript translations")
    javascript_locations = []
    # find translations directory
    for translation_directory in package_path.glob("**/translations"):
        # find i18next.js inside it
        for i18next_js in translation_directory.glob("**/i18next.js"):
            if (i18next_js.parent / "package.json").exists():
                click.secho(f"        Found translations at {i18next_js.parent.relative_to(package_path)}")
                javascript_locations.append(i18next_js.parent)

    # install the venv for the package
    click.secho(f"      Installing package")
    run_command(["python", "-m", "venv", ".venv"], cwd=package_path)
    venv_bin = package_path / ".venv" / "bin"
    pip_bin = venv_bin / "pip"

    # need older pip because of invenio-records-files
    run_command([pip_bin, "install", "-U", "setuptools", "pip==24.0", "wheel"], cwd=package_path)

    # install the package in editable mode
    run_command([pip_bin, "install", "-e", "."], cwd=package_path)

    if download_translations and definition.get('translations'):
        download_and_build_translations(package_path, venv_bin, javascript_locations)

    # build the package
    click.secho(f"      Building package")
    run_command([venv_bin / "python", "setup.py", "sdist", "bdist_wheel"],
                   cwd=package_path)

    # install the package to the repository
    click.secho(f"      Installing to RDM repository")
    repository.install_package(package_path, output=log_stream)


def download_and_build_translations(package_path, venv_bin, javascript_locations):
    if not (package_path / ".tx").exists():
        return

    setup_cfg = (package_path / "setup.cfg").read_text()
    if '[compile_catalog]' not in setup_cfg:
        click.secho(f"      No translations support found in setup.cfg, but transifex is present", fg="red")
        return

    # pull from transifex
    click.secho(f"      Pulling translations")
    run_command(["tx", "pull", "-a"], cwd=package_path)
    fix_rdm_records(package_path)
    # compile the translations
    click.secho(f"      Compiling catalog")
    run_command([venv_bin / "python", "setup.py", "compile_catalog"],
                cwd=package_path)
    # find translations directory
    for javascript_location in javascript_locations:
        # install the dependencies
        click.secho(f"      Compiling javascript translations at {javascript_location.relative_to(package_path)}")
        fix_nonexistent_translations(javascript_location)
        click.secho(f"      Installing i18next.js dependencies")
        run_command(["npm", "install"], cwd=javascript_location)
        click.secho(f"      Compiling i18next.js")
        run_command(["npm", "run", "compile_catalog"], cwd=javascript_location)


def fix_rdm_records(path):
    for f in (path / 'invenio-rdm-records').glob("**/*.po"):
        relative_path = f.relative_to(path)

        target_f = Path(str(relative_path).replace('invenio-rdm-records', 'invenio_rdm_records'))
        target_f = path / target_f
        target_f.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, target_f)

def fix_nonexistent_translations(javascript_path):
    message_directories = javascript_path / 'messages'
    for language_dir in message_directories.iterdir():
        if not language_dir.is_dir():
            continue
        if not (language_dir / 'messages.po').exists():
            click.secho(f"      Do not have po file for language {language_dir.name}, creating an empty one", fg="yellow")
            (language_dir / 'messages.po').write_text(f"""msgid ""\nmsgstr ""\n""")

    package_json = json.loads((javascript_path / 'package.json').read_text())
    languages = package_json.get("config", {}).get('languages', [])
    for lang in languages:
        language_dir = message_directories / lang
        if not language_dir.exists():
            click.secho(f"      Creating directory for language {lang}", fg="red")
            language_dir.mkdir(parents=True, exist_ok=True)

        if not (language_dir / 'messages.po').exists():
            click.secho(f"      Do not have po file for language {language_dir.name}, creating an empty one", fg="yellow")
            (language_dir / 'messages.po').write_text(f"""msgid ""\nmsgstr ""\n""")



if __name__ == "__main__":
    apply_patches()