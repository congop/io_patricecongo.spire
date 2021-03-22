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
from typing import List, NamedTuple

from ansible_collections.io_patricecongo.spire.plugins.module_utils import strings


class User(NamedTuple):
    name: str
    uid: int
    guid: int
    home: str

    @staticmethod
    def from_passwd_entry(passwd_entry:str)->"User":
        # stdout -> me:x:1000:1000:me,,,:/home/me:/bin/bash
        #        -> "root:x:0:0:root:/root:/bin/bash"
        trimmed = strings.trim_to_none(passwd_entry)
        splits = trimmed.split(":")
        name = splits[0]
        home = splits[-2]
        uid  = int(splits[2])
        guid = int(splits[3])
        return User(guid=guid, home=home, name=name, uid=uid)

    def __systemd_non_root_conf_dir(self) -> str:
        conf_dir = os.path.join(self.home, ".config/systemd/user")
        return conf_dir

    def is_root(self) -> bool:
        return 0 == self.uid

    def system_dirs(self) -> List[str]:
        if self.is_root():
            return [self.home]
        return [self.home, self.__systemd_non_root_conf_dir()]