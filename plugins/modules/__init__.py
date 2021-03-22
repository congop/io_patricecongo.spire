#
# Copyright (c) 2021 Patrice Congo <@congop>.
#
# This file is part of io_patricecongo.spire
# (see https://github.com/congop/io_patricecongo.spire).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.#
import os
import pkgutil

import pkg_resources


def read_version() -> str:
    package_dir = os.path.dirname(os.path.realpath(__file__))  # .rsplit(os.sep, 3)[0]
    config_path = os.path.join(package_dir, 'VERSION')
    with open(config_path) as version_file:
        return version_file.read().strip()


__version__: str = read_version()
