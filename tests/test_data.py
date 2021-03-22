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

""" """
from typing import List


spire_version="0.10.1"

spire_version_upgrade="0.11.2"

def test_versions() -> List[str]:
    return [spire_version, spire_version_upgrade]

def is_test_version(candidate_version) -> bool:
    return bool(
        candidate_version == spire_version
        or candidate_version == spire_version_upgrade
    )

def assert_is_test_version(spire_version:str):
        if not is_test_version(spire_version):
            msg = str(
                f"spire_version(={spire_version}) not supported; "
                f"supported values are {test_versions()}"
            )
            raise ValueError(msg)