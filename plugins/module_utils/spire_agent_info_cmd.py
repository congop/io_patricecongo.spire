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
import re
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, cast

from . import certificates, logging, spire_cmd, systemd
from .ansible_module_cmd import RunCommand
from .spire_typing import (
    BoolResultWithIssue, State,
    StateOfAgent,
    SubStateAgentRegistered,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)

from .systemd import(
    Scope, SpireComponentService, detect_spire_service_scope
)

class SpireAgentInfo:

    def __init__(
        self,
        run_command: RunCommand,
        log_func: Callable[[str, Optional[Dict[str,str]]], None],
        config_dir: str,
        data_dir: str,
        install_dir: str,
        service_name: str,
        service_scope:str = None,
        socket_path: str = None,
        expected_version: Optional[str] = None,
        file_exists_func: Callable[[str],bool] = os.path.exists,
    ) -> None:
        super().__init__()
        if not (config_dir and data_dir and install_dir
                and run_command and log_func and service_name
                and service_scope in [None, "user", "system", "global"]
                ):
            msg = f""" spire_agent data mus all be non blank:
                config_dir={config_dir}
                data_dir={data_dir}
                install_dir={install_dir}
                service_name={service_name}
            """
            raise RuntimeError(msg)
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.install_dir = install_dir
        self.run_command: RunCommand = run_command
        self.log_func = log_func
        self.executable:str = os.path.join(install_dir, "bin", "spire-agent")
        self.config_file_path:str = os.path.join(config_dir, "agent.conf")
        self.service_fullname = service_name
        if not service_name.endswith(".service"):
            self.service_fullname = f"{service_name}.service"
        self.expected_version = expected_version
        self.service_scope, self.service_scope_issue = detect_spire_service_scope(
            run_command=self.run_command,
            service_fullname=self.service_fullname
        )
        self.service_scope_cmd_arg_list = [] if not self.service_scope else [self.service_scope.systemctl_cmd_arg]

        self.file_exists_func: Callable[[str],bool] = file_exists_func
        self.executable_exists:bool = file_exists_func(self.executable)
        self.config_file_exists:bool = file_exists_func(self.config_file_path)
        self.version: Tuple[Optional[str],Optional[str]] = self.get_agent_version()
        self.socket_path:str = socket_path
        self.re_matching_is_healthy: Pattern[str] = re.compile(r".*Agent\sis\shealthy.*")

        self.service = SpireComponentService(
            log_func=log_func,
            run_command=run_command,
            scope=Scope.scopeOrDefault(self.service_scope, service_scope),
            service_name=self.service_fullname
        )

    def reset_computed_base_state(self) -> None:
        self.executable_exists = self.file_exists_func(self.executable)
        self.config_file_exists = self.file_exists_func(self.config_file_path)
        self.version = self.get_agent_version()

    def __str__(self) -> str:
        return str(self.__dict__)

    def get_executable_path(self)->str:
        return self.executable

    def get_executable_path_exists(self) -> bool:
        return bool(self.executable) and  os.path.exists(self.executable)

    def get_executable_path_does_not_exists_msg(self) -> str:
        return f"spire_executable[{self.executable}] does not exits"

    def get_agent_version(self) -> Tuple[Optional[str],Optional[str]]:
        return spire_cmd.get_pire_executable_version(
            executable_path=self.get_executable_path(),
            executable_exists_func= lambda : self.executable_exists,
            executable_path_does_not_exists_msg_func=self.get_executable_path_does_not_exists_msg,
            run_command=self.run_command
        )

    def is_agent_healthy(self) -> Tuple[Optional[bool], Optional[str]]:
        if not self.executable_exists:
            return None, self.get_executable_path_does_not_exists_msg()
        return spire_cmd.is_spire_component_healthy(
            healthcheck_cmd_output_regex=self.re_matching_is_healthy,
            ipc_socket_path_args=spire_cmd.ipc_socket_path_args_agent(self.socket_path),
            run_command=self.run_command,
            spire_component_bin=self.executable
        )

    def get_agent_spiffe_id_and_sertial_number(self) -> Tuple[Optional[str],Optional[int], Optional[str]]:
        """ return agent spiffe-i,serial-number,None or None,None,<error txt> """
        agent_svid_der_path = os.path.join(self.data_dir, "agent_svid.der")
        return certificates.get_cert_san(agent_svid_der_path)

    def get_trust_domain_id(self) -> Tuple[Optional[str],Optional[str]]:
        agent_svid_der_path = os.path.join(self.data_dir, "bundle.der")
        trust_domain, serial_nr, issue = certificates.get_cert_san(agent_svid_der_path)
        return trust_domain, issue

    def is_service_running(self) -> Tuple[Optional[bool],  Optional[str]]:
        res:BoolResultWithIssue = self.service.is_active()
        return res

    def is_service_enabled(self) -> Tuple[Optional[bool],  Optional[str]]:
        res:BoolResultWithIssue = self.service.is_enabled()
        return res

    def is_service_installed(self)  -> Tuple[Optional[bool],  Optional[str]]:
        return systemd.is_service_installed(
            run_command=self.run_command,
            service_fullname=self.service_fullname,
            service_scope=self.service_scope,
        )


    def is_agent_installed(self) -> Tuple[Optional[bool], Optional[str]]:
        actual_version = None if not self.version else self.version[0]
        expected_version_installed = not self.expected_version or self.expected_version == actual_version
        return self.executable_exists and self.config_file_exists and expected_version_installed, None

    def assert_agent_and_srv_are_installed(self) -> None:
        res_agent_installed = self.is_agent_installed()
        res_srv_installed = self.is_service_installed()
        if not (res_agent_installed[0] and res_srv_installed[0]):
            raise RuntimeError(
                f"agent and its service must be install, but found otherwise: "
                f"agent-installed:{res_agent_installed} "
                f"service-installed:{res_srv_installed}"
                )


class AgentStateSnapshot:

    def __init__(self, agent_info: SpireAgentInfo):
        _is_agent_installed = agent_info.is_agent_installed()
        self.spire_agent_installed = _is_agent_installed[0]
        self.spire_agent_installed_issue = _is_agent_installed[1]

        _spiffe_id_and_sn = agent_info.get_agent_spiffe_id_and_sertial_number()
        self.spire_agent_spiffe_id = _spiffe_id_and_sn[0]
        self.spire_agent_serial_number = _spiffe_id_and_sn[1]
        self.spire_agent_spiffe_id_issue = _spiffe_id_and_sn[2]

        _agent_version = agent_info.get_agent_version()
        self.spire_agent_version = _agent_version[0]
        self.spire_agent_version_issue = _agent_version[1]

        self.spire_agent_executable_path = agent_info.get_executable_path()

        _trust_domain_id = agent_info.get_trust_domain_id()
        self.spire_agent_trust_domain_id = _trust_domain_id[0]
        self.spire_agent_trust_domain_id_issue = _trust_domain_id[1]

        _is_service_healthy = agent_info.is_agent_healthy()
        self.spire_agent_is_healthy = _is_service_healthy[0]
        self.spire_agent_is_healthy_issue = _is_service_healthy[1]

        _is_service_installed = agent_info.is_agent_installed()
        self.spire_agent_service_installed = _is_service_installed[0]
        self.spire_agent_service_installed_issue = _is_service_installed[1]

        _is_service_running =  agent_info.is_service_running()
        self.spire_agent_service_running:bool = _is_service_running[0]
        self.spire_agent_service_running_issue:str = _is_service_running[1]

        _is_service__enabled =  agent_info.is_service_enabled()
        self.spire_agent_service_enabled: bool = _is_service__enabled[0]
        self.spire_agent_service_enabled_issue = _is_service__enabled[1]

        self.service_scope = agent_info.service_scope
        self.service_scope_issue = agent_info.service_scope_issue

    def get_issues_issues(self) -> str:
        issues_str = "\n".join([value for key,value in self.__dict__.items() if key.endswith("_issue") and value])
        return issues_str or None

    def get_state_registered(self) -> SubStateAgentRegistered:
        # The registration status cannot be retrieved,
        # because it is int the server data.
        # we therefore return None.
        # We do not try to use the heuristic (is_running and healthy) to infer registration state
        return SubStateAgentRegistered.indeterminable

    def get_state(self) -> State:
        if self.spire_agent_installed:
            return State.present
        else:
            return State.absent

    def get_state_service_status(self) -> SubStateServiceStatus:
        if self.spire_agent_is_healthy:
            return SubStateServiceStatus.healthy
        elif self.spire_agent_service_running:
            return SubStateServiceStatus.started
        else:
            return SubStateServiceStatus.stopped

    def get_state_service_installation(self) -> SubStateServiceInstallation:
        if self.spire_agent_service_enabled:
            return SubStateServiceInstallation.enabled
        elif self.spire_agent_installed:  # TODO fix me should be agent service installed
            return SubStateServiceInstallation.installed
        else:
            return SubStateServiceInstallation.not_installed

    def get_state_of_agent(self) -> StateOfAgent:
        return StateOfAgent(
            state=self.get_state(),
            substate_agent_registered=self.get_state_registered(),
            substate_service_installation=self.get_state_service_installation(),
            substate_service_status=self.get_state_service_status()
        )

    def __get_scope_str(self) -> str:
        if self.service_scope is not None:
            return self.service_scope.scope()
        return None

    def to_ansible_result(self) -> Dict[str, Any]:
        return {
            "spire_agent_installed": self.spire_agent_installed,
            "spire_agent_installed_issue": self.spire_agent_installed_issue,
            "spire_agent_spiffe_id": self.spire_agent_spiffe_id,
            "spire_agent_serial_number": self.spire_agent_serial_number,
            "spire_agent_spiffe_id_issue": self.spire_agent_spiffe_id_issue,
            "spire_agent_version": self.spire_agent_version,
            "spire_agent_version_issue": self.spire_agent_version_issue,
            "spire_agent_executable_path": self.spire_agent_executable_path,
            "spire_agent_trust_domain_id": self.spire_agent_trust_domain_id,
            "spire_agent_trust_domain_id_issue": self.spire_agent_trust_domain_id_issue,
            "spire_agent_is_healthy": self.spire_agent_is_healthy,
            "spire_agent_is_healthy_issue": self.spire_agent_is_healthy_issue,
            "spire_agent_service_scope": self.__get_scope_str(),
            "spire_agent_service_scope_issue": self.service_scope_issue,
            "spire_agent_service_installed": self.spire_agent_service_installed,
            "spire_agent_service_installed_issue": self.spire_agent_service_installed_issue,
            "spire_agent_service_running": self.spire_agent_service_running,
            "spire_agent_service_running_issue": self.spire_agent_service_running_issue,
            "spire_agent_service_enabled": self.spire_agent_service_enabled,
            "spire_agent_service_enabled_issue": self.spire_agent_service_enabled_issue
        }
