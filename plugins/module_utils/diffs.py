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
from abc import(
    ABC,
    abstractmethod
)
from typing import Callable, Dict, Iterable, List, Mapping
import itertools

from . import strings


class DiffABC(ABC):

    def __init__(self, resource_id: str, no_diff: bool) -> None:
        self.__no_diff: bool = no_diff
        self.resource_id: str = strings.trim_to_none(resource_id)

    def no_diff(self) -> bool:
        return self.__no_diff

    def get_resource_id(self) -> str:
        return self.resource_id

    @abstractmethod
    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        pass

    @staticmethod
    def to_ansible_diff_header_before_after_list(
        diffs: Iterable["DiffABC"]
    ) -> List[Dict[str, str]]:
        return [
            diff.ansible_diff_header_before_after()
            for diff in diffs
            if not diff.no_diff()
        ]

    @staticmethod
    def no_diff_from_iterables(*diffs: Iterable["DiffABC"]) -> bool:
        no_diffs = map(DiffABC.no_diff, itertools.chain(*diffs))
        return all(no_diffs)

    @staticmethod
    def predicate_diffing_resource(resource_id: str) -> Callable[["DiffABC"], bool]:
        def diffing_resource(diff: DiffABC) -> bool:
            return bool(resource_id == diff.resource_id)
        return diffing_resource

    @staticmethod
    def predicate_diffing_any_of(resource_ids: List[str]) -> Callable[["DiffABC"], bool]:
        def diffing_any_of(diff: DiffABC) -> bool:
            return diff.resource_id in resource_ids
        return diffing_any_of

    @staticmethod
    def need_change(
        file:str, diffs: Iterable["DiffABC"], diffs_label: str
    ) -> bool:
        for stat in diffs:
            if file == stat.resource_id:
                return not stat.no_diff()
        res_ids = list(map(DiffABC.get_resource_id, diffs))
        msg = f"no diff for [{file}] found in {diffs_label}, availabe are {res_ids}"
        raise ValueError(msg)

class StrResourceDiff(DiffABC):
    def __init__(
        self, resource_id: str, actual: str, expected: str
    ) -> None:
        t_actual = strings.trim_to_none(actual)
        t_expected = strings.trim_to_none(expected)
        no_diff: bool = t_actual == t_expected
        super().__init__(no_diff=no_diff, resource_id=resource_id)
        self.actual: str = t_actual
        self.expected: str = t_expected

    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        return {
             "after_header": f"{self.resource_id} ({self.expected})",
             "before_header": f"{self.resource_id} ({self.actual})"
        }

class DigestDiff(DiffABC):
    def __init__(
        self, file: str, digest_actual: str, digest_expected: str
    ) -> None:
        _digest_actual = strings.trim_to_none(digest_actual)
        _digest_expected = strings.trim_to_none(digest_expected)
        no_diff: bool = _digest_actual == _digest_expected
        super().__init__(no_diff=no_diff, resource_id=file)
        self.digest_actual: str = digest_actual
        self.digest_expected: str = _digest_expected

    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        file:str = self.resource_id
        return {
             "after_header": f"{file} (content disgest={self.digest_expected})",
             "before_header": f"{file} (content disgest={self.digest_actual})"
        }

class VersionDiff(DiffABC):
    def __init__(
        self, resource_id: str, version_actual: str, version_expected: str
    ) -> None:
        version_actual = strings.trim_to_none(version_actual)
        version_expected = strings.trim_to_none(version_expected)
        no_diff = version_actual == version_expected
        super().__init__(no_diff=no_diff, resource_id=resource_id)
        self.version_actual: str = strings.trim_to_none(version_actual)
        self.version_expected: str = strings.trim_to_none(version_expected)

    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        file:str = self.resource_id
        return {
             "after_header": f"{file} (version={self.version_expected})",
             "before_header": f"{file} (version={self.version_actual})"
        }