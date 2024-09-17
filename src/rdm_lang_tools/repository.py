#
# Copyright (C) 2024 CESNET z.s.p.o.
#
# rdm-lang-tools is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.
#
import abc
import configparser
import json
import os
import re
import shutil
import sys
from functools import cached_property
from pathlib import Path
from subprocess import CalledProcessError

import progressbar

from .redirected_subprocess import check_call, check_output


class Repository(abc.ABC):
    invenio_package_regexps = [
        "invenio-.*",
    ]

    def __init__(self, path, tmppath):
        self.path = path
        self.local_packages_path = tmppath / "local_packages"
        self.local_translations_path = tmppath / "local_translations"

    @property
    @abc.abstractmethod
    def installed_packages(self):
        pass

    def download_invenio_packages(self):
        bar = progressbar.ProgressBar(
            prefix="Downloading {variables.package_name} ",
            variables={"package_name": "---"},
            redirect_stderr=True,
            redirect_stdout=True,
        )
        for pkg_name, version in bar(self.invenio_packages.items()):
            bar.variables["package_name"] = pkg_name
            bar.update(bar.value, force=True)
            github_url = f"https://github.com/inveniosoftware/{pkg_name}"
            local_path = self.local_package_path(pkg_name)
            if local_path.exists():
                shutil.rmtree(local_path)
            self.download_package(github_url, version, local_path)

    def local_package_path(self, pkg_name):
        if not self.local_packages_path.exists():
            self.local_packages_path.mkdir(parents=True)
        local_path = self.local_packages_path / pkg_name
        return local_path

    def download_translations(self):
        unsuccessful_packages = []
        bar = progressbar.ProgressBar(
            prefix="Downloading translations for {variables.package_name} ",
            variables={"package_name": "---"},
            redirect_stderr=True,
            redirect_stdout=True,
        )
        for pkg_name, version in bar(self.invenio_packages.items()):
            print(f"Downloading translations for {pkg_name}@{version}")
            bar.variables["package_name"] = pkg_name
            bar.update(bar.value, force=True)
            pkg_path = self.local_package_path(pkg_name)
            if not (pkg_path / ".tx").exists():
                print(f"Skipping {pkg_name} because it does not have a .tx directory")
                continue

            resource_names = []
            # check the contents of the .tx/config file
            config = configparser.ConfigParser()
            config.read(pkg_path / ".tx" / "config")
            resources = config.sections()
            modified = False
            for resource in list(resources):
                if resource == "main":
                    continue
                if resource.startswith("o:"):
                    resource_names.append(resource)
                    continue
                print("Need to rename the resource", resource)
                if resource.startswith("invenio."):
                    new_resource = re.sub(
                        r"^invenio\.", "o:inveniosoftware:p:invenio:r:", resource
                    )
                    config[new_resource] = config[resource]
                    del config[resource]
                    modified = True
                    resource_names.append(new_resource)
            if modified:
                with open(pkg_path / ".tx" / "config", "w") as f:
                    config.write(f)

            for resource in resource_names:
                try:
                    resource = "invenio." + resource.rsplit(":", 1)[1]
                    check_call(
                        ["tx", "pull", "-a", "--force", "--silent", resource],
                        cwd=pkg_path,
                    )
                except CalledProcessError:
                    unsuccessful_packages.append((pkg_name, resource))
        for pkg in unsuccessful_packages:
            print(f"Failed to download translations for {pkg}", file=sys.stderr)

    def local_invenio_packages(self):
        ret = []
        for pkg_name, version in self.invenio_packages.items():
            local_path = self.local_package_path(pkg_name)
            if local_path.exists():
                ret.append((pkg_name, local_path))
        return ret

    def local_invenio_packages_with_translations(self):
        ret = []
        for pkg_name, local_path in self.local_invenio_packages():
            if (local_path / ".tx").exists():
                # read config to get translation paths
                config = configparser.ConfigParser()
                config.read(local_path / ".tx" / "config")
                for resource in config.sections():
                    if resource == "main":
                        continue
                    ret.append((pkg_name, local_path, config[resource]["file_filter"]))
        return ret

    def download_package(self, package_url, package_version, local_path):
        check_call(
            [
                "git",
                "clone",
                package_url,
                "--quiet",
                "--branch",
                f"v{package_version}",
                "--single-branch",
                local_path,
            ]
        )

    @cached_property
    def invenio_packages(self):
        ret = {}
        for package in self.installed_packages:
            for regexp in self.invenio_package_regexps:
                if re.match(regexp, package["name"]):
                    ret[package["name"]] = package["version"]
                    break
        return ret

    @abc.abstractmethod
    def install_editable(self, path):
        pass


class RepositoryWithPipfile(Repository):

    @cached_property
    def installed_packages(self):
        return json.loads(
            check_output(
                ["pipenv", "run", "pip", "list", "--format=json"],
                cwd=self.path,
                env={**os.environ, "PIPENV_IGNORE_VIRTUALENVS": "1"},
            )
        )

    def install_editable(self, path):
        check_call(
            ["pipenv", "run", "pip", "install", "--force", "--no-deps", "-e", path],
            cwd=self.path,
            env={**os.environ, "PIPENV_IGNORE_VIRTUALENVS": "1"},
        )


class RepositoryWithVenv(Repository):

    @cached_property
    def installed_packages(self):
        return json.loads(
            check_output([".venv/bin/pip", "list", "--format=json"], cwd=self.path)
        )

    def install_editable(self, path):
        check_call([".venv/bin/pip", "install", "--force", "--no-deps", "-e", path])


def get_repository(repository_directory, temp_directory):
    repository_directory = Path(repository_directory)
    if (repository_directory / "Pipfile").exists():
        return RepositoryWithPipfile(repository_directory, temp_directory)
    else:
        return RepositoryWithVenv(repository_directory, temp_directory)
