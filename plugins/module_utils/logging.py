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
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from ansible.module_utils.basic import AnsibleModule


class CachingLogger:
    def __init__(self, journal_log: Callable[[Any,Any], None]) -> None:
        self.messages: List[Any] =[]
        #self.ansible_module: AnsibleModule = ansible_module
        self.journal_log: Callable[[Any,Any], None] = journal_log

    def __call__(
        self,
        msg: str,
        log_args: Optional[Dict[str, str]] = None
    ) -> None:
        # if self.ansible_module._debug:
        self.messages.append(str(msg))
        self.journal_log(msg, log_args)


def caching_logger_func(
    module: AnsibleModule
) -> Callable[[str, Optional[Dict[str, str]]], None]:
    return CachingLogger(module.log)


def get_exception_stacktrace(e: Exception) -> str:
    import traceback
    st = traceback.format_exception(type(e), e, e.__traceback__)
    return "\n".join(st)


class Logger(ABC):

    @abstractmethod
    def v(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def vv(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def vvv(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def vvvv(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def vvvvv(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def vvvvvv(self, msg: Any, host: Any=None) -> None:
        pass

    @abstractmethod
    def debug(self, msg: Any, host: Any=None) -> None:
        pass
