#!/usr/bin/env python

##
## Copyright (c) 2021 Patrice Congo <@congop>.
##
## This file is part of io_patricecongo.spire
## (see https://github.com/congop/io_patricecongo.spire).
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/>.##

# TODO remove me or ensure alignment with ansible collection build peculiarities
from pathlib import Path

import setuptools

project_dir = Path(__file__).parent

setuptools.setup(
    name="ansible-modules-spire",
    version=project_dir.joinpath("plugins/modules/VERSION").read_text(encoding="utf-8"),#"1.0.0",
    description="Example Python project",
    # Allow UTF-8 characters in README with encoding argument.
    long_description=project_dir.joinpath("README.md").read_text(encoding="utf-8"),
    keywords=["ansible", "module","spiffe", "spire","python"],
    author="",
    url="https://github.com/congop/ansible-modules-spire",
    packages=setuptools.find_packages("plugins"),
    package_dir={"": "plugins"},
    package_data={
      '': ['plugins/modules/VERSION'],
    },
    python_requires=">=3.6",
    # There are some peculiarities on how to include package data for source
    # distributions using setuptools. You also need to add entries for package
    # data to MANIFEST.in.
    # See https://stackoverflow.com/questions/7522250/
    include_package_data=True,

    install_requires=project_dir.joinpath("requirements.txt").read_text().split("\n"),
    zip_safe=False,
    license="Apache 2",
    license_files=["LICENSE.txt"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers, DevOps",
        "License :: OSI Approved :: Apache License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    entry_points={"console_scripts": ["spire_spiffe_id=modules.spire_spiffe_id:main"]},
)



