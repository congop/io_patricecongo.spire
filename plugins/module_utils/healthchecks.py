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
import re
import time
from typing import Callable, List, Pattern

from ansible_collections.io_patricecongo.spire.plugins.module_utils import logging, spire_cmd
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    BoolResultWithIssue,
    CmdExecCallable,
    CmdExecOutcome,
)


class Check(ABC):

    def __init__(
        self,
        healthcheck_cmd_output_regex: Pattern[str],
        ipc_socket_path_args: List[str],
        run_command: CmdExecCallable,
        spire_component_bin:str,
        readiness_probe_timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__()
        self.readiness_probe_timeout_seconds = readiness_probe_timeout_seconds
        self.healthcheck_cmd_output_regex = healthcheck_cmd_output_regex
        self.ipc_socket_path_args = ipc_socket_path_args
        self.run_command = run_command
        self.spire_component_bin = spire_component_bin

    def is_healthy(self) -> BoolResultWithIssue:
        return spire_cmd.is_spire_component_healthy(
            healthcheck_cmd_output_regex=self.healthcheck_cmd_output_regex,
            ipc_socket_path_args=self.ipc_socket_path_args,
            run_command=self.run_command,
            spire_component_bin=self.spire_component_bin
        )

    def wait_for_readiness(self) -> None:
        """ Waits for the checked spire component to become healthy."""
        start = time.time()

        def has_not_timeout() -> bool:
            return time.time() - start < self.readiness_probe_timeout_seconds

        res_is_healthy: BoolResultWithIssue = self.is_healthy()
        res_has_not_timeout = True
        attempts = 0
        while (not res_is_healthy.res
               and res_has_not_timeout):
            time.sleep(1)
            attempts = attempts + 1
            res_is_healthy = self.is_healthy()
            res_has_not_timeout = has_not_timeout()
        res_is_healthy = self.is_healthy()

        if not res_is_healthy.res:
            raise RuntimeError(
                f"readiness probe failed:timeout={not res_has_not_timeout}"
                f", self.readiness_probe_timeout_seconds={self.readiness_probe_timeout_seconds}"
                f", health check:{res_is_healthy}"
                f", attempts={attempts}")


class CheckServer(Check):
    def __init__(
        self, run_command: CmdExecCallable,
        file_spire_server_bin: str,
        registration_uds_path: str,
        readiness_probe_timeout_seconds: float = 5.0
    ) -> None:
        super().__init__(
            run_command=run_command,
            healthcheck_cmd_output_regex=re.compile(r"^.*Server\sis\shealthy.*$"),
            ipc_socket_path_args=spire_cmd.ipc_socket_path_args_server(
                                                            registration_uds_path),
            spire_component_bin=file_spire_server_bin,
            readiness_probe_timeout_seconds=readiness_probe_timeout_seconds
        )


class CheckAgent(Check):
    def __init__(
        self, run_command: CmdExecCallable,
        file_spire_agent_bin: str,
        socket_path: str,
        readiness_probe_timeout_seconds: float = 5.0
    ) -> None:
        super().__init__(
            run_command=run_command,
            healthcheck_cmd_output_regex=re.compile(r"^.*Agent\sis\shealthy.*$"),
            ipc_socket_path_args=spire_cmd.ipc_socket_path_args_agent(socket_path),
            spire_component_bin=file_spire_agent_bin,
            readiness_probe_timeout_seconds=readiness_probe_timeout_seconds
        )