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
from packaging import version
from typing import Any, NamedTuple, NoReturn, Tuple, cast

def version_change_within_one_minor(
    v1: version.Version,
    v2: version.Version
) -> bool:
    return v1.major == v1.major and abs(v1.minor - v2.minor) <= 1

def is_version_0_12_x(v: version.Version) -> bool:
    return v is not None and 0 == v.major and 12 == v.minor

def is_version_1_0_x(v: version.Version) -> bool:
    return v is not None and 1 == v.major and 0 == v.minor

def version_jump_from_0_12_x_to_1_0_x(
    v1: version.Version,
    v2: version.Version
) -> bool:
    return is_version_0_12_x(v1) and is_version_1_0_x(v2)

def __assert_version_are_pep_440_version(
    current_version: Any,
    target_version: Any
) -> None:
    is_target_vers_lecacy = isinstance(target_version, version.LegacyVersion)
    is_current_vers_lecacy = isinstance(current_version, version.LegacyVersion)
    if  is_target_vers_lecacy or is_current_vers_lecacy :
        raise TypeError(
                f"""bad version format:
                    current_version={current_version}
                    target_version={target_version}
                """)

def __parse_versions_assuming_pep_440_version_format(
    current_version_str: str,
    target_version_str: str
) -> Tuple[version.Version,version.Version]:
    target_version = version.parse(target_version_str)
    current_version = version.parse(current_version_str)
    __assert_version_are_pep_440_version(
                current_version=current_version,
                target_version=target_version)
    return cast(version.Version, current_version), cast(version.Version, target_version)

def can_upgrade_or_downgrade(
    current_version_str: str,
    target_version_str: str
) -> bool:
    if not current_version_str or not target_version_str:
        raise TypeError(f"""version must be provided:
                            current_version={current_version_str}
                            target_version={target_version_str}
                        """)
    #spire uses semantic versioning
    # we are quite sure its format is compatible with pep-400-version-format parse
    target_vers, current_vers = __parse_versions_assuming_pep_440_version_format(
        current_version_str=current_version_str,
        target_version_str=target_version_str
    )

    return version_change_within_one_minor(current_vers, target_vers) \
            or version_jump_from_0_12_x_to_1_0_x(current_vers, target_vers) \
            or version_jump_from_0_12_x_to_1_0_x(target_vers, current_vers)
