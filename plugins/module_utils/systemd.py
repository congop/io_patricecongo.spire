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
import enum
import os
from typing import Callable, Dict, List, Optional, Any, Tuple

from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    BoolResultWithIssue,
    CmdExecCallable,
    CmdExecOutcome,
)





@enum.unique
class Scope(enum.Enum):
    def __init__(self, scope:str, systemctl_arg:str):
         self._value_ = scope
         self.__systemctl_arg: str = systemctl_arg

    scope_user = ("user", "--user")
    scope_system = ("system", "--system")
    scope_global = ("global", "--global")

    def systemctl_cmd_arg(self) -> str:
        return self.__systemctl_arg

    @classmethod
    def by_name(cls, name: str) -> Optional["Scope"]:
        """Returns the Scope corresponding to the given name.
        :param name the scope name, may be prefixed with scope_
        :return the found scope or None if there is no corresponding scope found
        """
        if name is None or name.isspace():
            return None
        scope_name = name.strip()
        if not scope_name.startswith("scope_"):
            scope_name = "scope_" + scope_name
        found_scope = cls.__members__.get(scope_name, None)
        return found_scope

    def scope(self) -> str:
        return str(self._value_)

    def get_default_installed_dir(self) -> str:
        if self == Scope.scope_system:
            return "/etc/systemd/system/"
        elif self == Scope.scope_user:
            return os.path.expandvars("${HOME}/.config/systemd/user/")
        elif self == Scope.scope_global:
            return "/usr/lib/systemd/user/"
        else:
            raise RuntimeError(
                f"scope({self}) not supported yet, cannot get default installed dir"
            )

    @staticmethod
    def scopeOrDefault(current_scope: "Scope", expected_scope_str:str) -> "Scope" :
        if current_scope is not None:
            return current_scope
        found_scope = Scope.by_name(expected_scope_str)
        return found_scope or Scope.scope_system

    @staticmethod
    def noneOrScope(scope: "Scope") -> str:
        if scope is None:
            return None
        return scope.scope()

#TODO us Scope type; make it mandatory
def is_service_installed(
    run_command: Callable[[Any], Tuple[int, str, str]],
    service_fullname: str,
    service_scope:  Scope
) -> Tuple[Optional[bool],  Optional[str]]:
    """Check whether a service specified by its full-name and scope is installed.
    Params:
        run_command: callable used to execute processes
        service_fullname:
        service_scope
    Returns:
        a tuple (is_installed, msg) indicating the outcome of the check.
        is_installed:
            true if the service is installed
            false if the service is not installed,
            None if the systemcl command failed
        msg:
            a message containing std-out and std-err if is_installed is not true

    """

    # Because the service may be loaded but inactive (e.g. the service file has just been copied)
    # <systemctl show pattern> will not always answer the installation question correctly
    # we are using <systemctl list_unit-files> instead:
    # Example:
    #   $ systemctl --user list-unit-files spire_agent_unit_test.service
    #   UNIT FILE                     STATE
    #   spire_agent_unit_test.service disabled

    # 1 unit files listed.
    pattern = service_fullname
    service_scope_cmd_arg_list = [] if not service_scope else [service_scope.systemctl_cmd_arg()]
    args = [
        "systemctl", *service_scope_cmd_arg_list,
        "list-unit-files", pattern,
    ]
    rc, stdout, stderr = run_command(args)
    if rc != 0:
        return None, f"failed to systemctl-list-unit-files: rc={rc} cmd={args}, stdout={stdout} stderr={stderr}"
    is_installed: bool = service_fullname in stdout
    msg = None if is_installed else f"systemctl-show-names: rc={rc} cmd={args}, stdout={stdout} stderr={stderr}"
    return is_installed, msg

def detect_spire_service_scope(
    run_command: Callable[[Any],Tuple[int,str, str]],
    service_fullname: str,
) -> Tuple[Optional[Scope], Optional[str]] :
    issues = []
    for scope in Scope:
        installed: Tuple[Optional[bool], Optional[str]] = is_service_installed(
                                                run_command=run_command,
                                                service_fullname=service_fullname,
                                                service_scope=scope)
        if installed is not None and installed[0]:
            return scope, None
        issues.append(installed[1] or "")
    return None, "".join(issues)


class SpireComponentService:
    def __init__(
        self,
        service_name: str,
        run_command: CmdExecCallable,
        scope: Scope = Scope.scope_system,
        log_func: Callable[[str, Optional[Dict[str, str]]], None] = None,
    ) -> None:
        self.service_name = service_name
        self.service_full_name = service_name
        if not self.service_full_name.endswith(".service"):
            self.service_full_name = f"{self.service_full_name}.service"
        self.run_command: CmdExecCallable = run_command
        self.scope = scope
        self.install_dir: str = scope.get_default_installed_dir() # "/etc/systemd/system/"
        if scope == Scope.scope_user:
            os.makedirs(self.install_dir, mode=0o770, exist_ok=True)
        self.service_file = os.path.join(self.install_dir, self.service_full_name)
        self.log_func: Callable[[str, Optional[Dict[str, str]]], None] = log_func

    def __run_cmd(self, args: List[str]) -> CmdExecOutcome:
        rc, stdout, stderr = self.run_command(args)
        self.__log(f"{args} --> {rc}, {stdout}, {stderr}, {args}")
        return CmdExecOutcome(rc, stdout, stderr)

    def __log(self, msg: str) -> None:
        if self.log_func is not None:
            self.log_func(msg, None)

    def __run_unit_file_cmd(self, action: str) -> CmdExecOutcome:
        args = ["systemctl", *self.__scope_args(), action, self.service_full_name]
        outcome: CmdExecOutcome = self.__run_cmd(args)
        return outcome

    def exec_systemctl_show_srv_name(self) -> CmdExecOutcome:
        # systemctl --user show '*spire_agent_unit_test.service*' --no-pager --property=Names --value; echo $?
        # spire_agent_unit_test.service
        pattern = f"*{self.service_full_name}*"
        res: CmdExecOutcome = self.__run_cmd(
            [
                "systemctl", *self.__scope_args(), "show", pattern, "--no-pager",
                "--property=Names", "--value"
            ]
        )
        return res

    @staticmethod
    def is_service_not_installed(res: CmdExecOutcome) -> bool:
        # <systemctl show .. -properties=Names> issues no output if the service is not installed;
        # and the service full names (yes! plural) is it is
        return bool(res.succeeded()
                    and res.has_blank_stdout_and_stderr())

    def remove_service_file(self) -> str:
        if os.path.exists(self.service_file):
            try:
                os.remove(self.service_file)
            except Exception as e:
                return f"Failed to remove service file:{self.service_file} -- Exception:{str(e)}"
        return None

    def __scope_args(self) -> List[str]:
        return [self.scope.systemctl_cmd_arg()]

    def enable(self) -> None:
        args = ["systemctl", *self.__scope_args(), "enable", self.service_full_name]
        outcome: CmdExecOutcome = self.__run_cmd(args)
        if outcome.failed():
            msg = f"""failed to enable service[{self.service_full_name}]:
                    outcome={outcome}
                    args={args}
                    """
            raise RuntimeError(msg)

    def is_enabled(self) -> BoolResultWithIssue:
        res = self.__run_unit_file_cmd("is-enabled")
        if res.failed():
            issue = f"Fail to execute <systemctl is-enabled ...>:{res}"
            return BoolResultWithIssue(False, issue)

        if "enabled" != str(res.stdout).strip():
            issue = f"service found not to be enabled:{res}"
            return BoolResultWithIssue(False, issue)
        return BoolResultWithIssue(True, None)

    def is_active(self) -> BoolResultWithIssue:
        res = self.__run_unit_file_cmd("is-active")
        if res.failed():
            issue = f"Fail to execute <systemctl is-active ...>:{res}"
            return BoolResultWithIssue(False, issue)

        if "active" != str(res.stdout).strip():
            issue = f"service found not to be active:{res}"
            return BoolResultWithIssue(False, issue)
        return BoolResultWithIssue(True, None)

    def start(self) -> None:
        args = ["systemctl", *self.__scope_args(), "start", self.service_full_name]
        outcome: CmdExecOutcome = self.__run_cmd(args)
        if outcome.failed():
            msg = f"""failed to start service[{self.service_full_name}]:
                    outcome={outcome}
                    args={args}
                    whoami={self.__run_cmd(["whoami"])}
                    """
            raise RuntimeError(msg)

    def stop(self) -> None:
        args = ["systemctl", *self.__scope_args(), "stop", self.service_full_name]
        outcome: CmdExecOutcome = self.__run_cmd(args)
        if outcome.failed():
            msg = f"""failed to stop service[{self.service_full_name}]:
                    outcome={outcome}
                    args={args}
                    """
            raise RuntimeError(msg)

    def teardown_service(self) -> None:
        res_show_srv_name: CmdExecOutcome = self.exec_systemctl_show_srv_name()
        if SpireComponentService.is_service_not_installed(res_show_srv_name):
            self.__log(f"Not installed: skipping teardown of {self.service_name}: {res_show_srv_name}")
            return

        res_stop: CmdExecOutcome = self.__run_unit_file_cmd("stop")
        res_disable: CmdExecOutcome = self.__run_unit_file_cmd("disable")
        rm_srv_file_msg = self.remove_service_file()
        res_daemon_reload: CmdExecOutcome = self.__run_cmd(["systemctl", *self.__scope_args(), "daemon-reload"])
        res_reset_failed: CmdExecOutcome = self.__run_unit_file_cmd("reset-failed")

        res_show_srv_name = self.exec_systemctl_show_srv_name()
        installed: Tuple[Optional[bool], Optional[str]] = is_service_installed(
                                                run_command=self.run_command,
                                                service_fullname=self.service_full_name,
                                                service_scope=self.scope)
        if installed[0]: # SpireComponentService.is_service_not_installed(res_show_srv_name):
            msg = f"""Fail to remove service {self.service_full_name}
                outcome_stop:{res_stop}
                outcome_disable:{res_disable}
                rm_srv_file_msg :{rm_srv_file_msg}
                outcome_daemon_reload:{res_daemon_reload}
                outcome_reset_failed:{res_reset_failed}
                installed: {installed}
            """
            raise RuntimeError(msg)
