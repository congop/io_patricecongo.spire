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
import time
from typing import Any, Callable, List, Optional, Pattern, Tuple

from . import logging
from .spire_typing import BoolResultWithIssue, CmdExecCallable, CmdExecOutcome


def get_pire_executable_version(
    run_command: Callable[[Any],Tuple[int,str, str]],
    executable_path: str,
    executable_exists_func: Callable[[], bool],
    executable_path_does_not_exists_msg_func: Callable[[], str]
) -> Tuple[Optional[str],Optional[str]]:
    try:
        if not executable_exists_func():
            return None, executable_path_does_not_exists_msg_func()

        args = [executable_path, "--version"]
        rc, stdout, stderr = run_command(args)
        if rc != 0:
            return None, f"fail t execute command:{args}, stdout={stdout}, stderr={stderr}"
        # version is actually in stderr (as of version 0.10.0),
        # but we default to stdout in case it changed to be in stdout
        version = stderr or stdout
        if version:
            version = version.strip()
        return version, None
    except Exception as e:
        st = logging.get_exception_stacktrace(e)
        msg = f"{str(e)} --- {st}"
        return None, msg

def ipc_socket_path_args_agent(socket_path:str) -> List[str]:
        if not socket_path:
            return []
        return ["-socketPath", socket_path]

def ipc_socket_path_args_server(registration_uds_path:str) -> List[str]:
        if not registration_uds_path:
            return []
        return ["-registrationUDSPath", registration_uds_path]

def is_spire_component_healthy(
    run_command: CmdExecCallable,
    spire_component_bin: str,
    ipc_socket_path_args: List[str],
    healthcheck_cmd_output_regex: Pattern[str]
) -> BoolResultWithIssue:
    """check health of a spire component(spire-server/agent).
    Params:
        run_command: a CmdExecCallable which provide the mechanism to run health check command
        spire_component_bin: path to the component binary,
        ipc_socket_path_args: list containing the arg to specify the socket for ipc with the spire component
        healthcheck_cmd_output_regex: regex Pattern to check the output for healthyness state
    """
    cmd_healthy_args = [
        spire_component_bin, "healthcheck",
        *ipc_socket_path_args
    ]
    try:
        res: CmdExecOutcome = run_command(cmd_healthy_args)
    except FileNotFoundError as e:
        return BoolResultWithIssue(
            False,
            f"""error executing [{cmd_healthy_args}]:
                error: {str(e)}
                {logging.get_exception_stacktrace(e)
            }""")
    if res.failed() or not healthcheck_cmd_output_regex.match(str(res.stdout)):
        issue = f"""stdout:{res.stdout}
                stderr:{res.stderr}
                args: {cmd_healthy_args}
                """
        return BoolResultWithIssue(False, issue)
    return BoolResultWithIssue(True, None)


def wait_for_termination(
    is_terminated_func: Callable[[], bool],
    termination_probe_timeout_seconds: float = None
) -> BoolResultWithIssue:
    start = time.time()

    def has_not_timeout() -> bool:
        return time.time() - start < termination_probe_timeout_seconds

    res_has_not_timeout = True
    while (
            not is_terminated_func()
            and res_has_not_timeout):
        time.sleep(1)
        res_has_not_timeout = has_not_timeout()

    if not is_terminated_func():
        msg = f"termination probe failed:timeout={not res_has_not_timeout}"
        return BoolResultWithIssue(False, msg)
    return BoolResultWithIssue(True, None)
