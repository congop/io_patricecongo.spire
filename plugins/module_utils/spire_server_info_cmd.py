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

from ansible_collections.io_patricecongo.spire.plugins.module_utils.ansible_module_cmd import RunCommand

from . import certificates, logging, spire_cmd, systemd
from .spire_typing import (
    BoolResultWithIssue, State,
    StateOfServer,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)

from .digests import(
    digest_hcl_file,
    digest_ini_file
)

from .systemd import (
    Scope, SpireComponentService, detect_spire_service_scope
)

from .file_stat import(
    FileStats, FileModes
)

class ServerDirs:

    def __init__(self,
        config_dir: str,
        data_dir: str,
        install_dir: str,
        service_dir: str,
        log_dir: str,
        service_name: str,
    ) :
        self.config_dir: str = os.path.normpath(config_dir)
        self.data_dir: str = os.path.normpath(data_dir)
        self.install_dir: str = os.path.normpath(install_dir)
        self.install_dir_bin: str = None
        if install_dir:
            self.install_dir_bin = os.path.join(self.install_dir, "bin")
        self.service_dir: str = os.path.normpath(service_dir)
        self.log_dir: str = os.path.normpath(log_dir)
        self.service_name = service_name
        # TODO this should be service_full_name
        self.service_filename = service_name
        if service_name:
            if service_name.endswith(".service"):
                self.service_name = os.path.splitext(service_name)[0]
            else:
                self.service_filename = f"{service_name}.service"
        self.path_conf_file: str = os.path.join(self.config_dir, "server.conf")
        self.path_env_file: str = os.path.join(self.config_dir, "server.env")
        self.path_trust_bundle_pem: str = os.path.join(self.config_dir, "trust_bundle.pem")
        self.path_service_file: str = os.path.join(self.service_dir, self.service_filename)
        self.path_executable: str = os.path.join(self.install_dir_bin, "spire-server")

    @staticmethod
    def from_ansible_src(value_lookup_func: Callable[[str], str]) -> "ServerDirs":
        dirs = ServerDirs(
            config_dir = value_lookup_func("spire_server_config_dir"),
            data_dir = value_lookup_func("spire_server_data_dir"),
            install_dir = value_lookup_func("spire_server_install_dir"),
            service_dir = value_lookup_func("spire_server_service_dir"),
            log_dir  = value_lookup_func("spire_server_log_dir"),
            service_name = value_lookup_func("spire_server_service_name")
        )
        return dirs

    def __str__(self) -> str:
        return f"ServerDirs({self.__dir__})"


    def expected_dirs(self) -> List[str]:
        return [
            self.config_dir,
            self.data_dir,
            self.install_dir,
            self.install_dir_bin,
            self.service_dir,
            self.log_dir,
        ]

    def expected_files_not_exec(self) -> List[str]:
        return [
            self.path_conf_file,
            self.path_env_file,
            self.path_service_file,
            #self.path_trust_bundle_pem()
        ]

    def expected_files_exec(self) -> List[str]:
        return [
            self.path_executable,
        ]

    def expected_dirs_and_files(self) -> List[str]:
        return [
            *self.expected_dirs(),
            *self.expected_files_not_exec(),
            *self.expected_files_exec()
        ]

    def mode_to_expected_dirs(
        self, file_modes: FileModes
    ) -> Dict[str,List[str]]:
        return {file_modes.mode_dir: self.expected_dirs()}

    def mode_to_expected_files(
        self, file_modes: FileModes
    ) -> Dict[str,List[str]]:
        mode_to_file_mapping: List[Tuple[str,List[str]]] = [
                (file_modes.mode_file_not_exe, self.expected_files_not_exec()),
                (file_modes.mode_file_exe, self.expected_files_exec()),
        ]
        mtf: Dict[str,List[str]] = {}
        for mode, files in mode_to_file_mapping:
            tfiles = mtf.get(mode)
            if tfiles is None:
                tfiles = []
                mtf[mode] = tfiles
            tfiles.extend(files)
        return mtf


class SpireServerInfo:

    def __init__(
        self,
        run_command: RunCommand,
        log_func: Callable[[str, Optional[Dict[str,str]]], None],
        server_dirs:ServerDirs,
        service_name: str,
        service_scope:str = None,
        registration_uds_path: str = None,
        expected_version: Optional[str] = None,
        file_exists_func: Callable[[str],bool] = os.path.exists,
    ) -> None:
        super().__init__()
        if not (server_dirs.config_dir and server_dirs.data_dir and server_dirs.install_dir
                and run_command and log_func and service_name
                and service_scope in [None, "user", "system", "global"]
                ):
            msg = f""" spire_server data mus all be non blank:
                config_dir={server_dirs.config_dir}
                data_dir={server_dirs.data_dir}
                install_dir={server_dirs.install_dir}
                service_name={service_name}
            """
            raise RuntimeError(msg)
        self.server_dirs: ServerDirs = server_dirs
        self.run_command: RunCommand = run_command
        self.log_func = log_func
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
        self.executable_exists:bool = file_exists_func(self.server_dirs.path_executable)
        self.config_file_exists:bool = file_exists_func(self.server_dirs.path_conf_file)
        self.version: Tuple[Optional[str],Optional[str]] = self.get_version()
        self.registration_uds_path:str = registration_uds_path
        self.re_matching_is_healthy: Pattern[str] = re.compile(r".*Server\sis\shealthy.*")

        self.service = SpireComponentService(
            log_func=log_func,
            run_command=run_command,
            scope=Scope.scopeOrDefault(self.service_scope, service_scope),
            service_name=self.service_fullname
        )

    def get_local_server_file_stats(self) -> FileStats:
        return FileStats.get_local_stats(self.server_dirs.expected_dirs_and_files())

    def reset_computed_base_state(self) -> None:
        self.executable_exists = self.file_exists_func(self.server_dirs.path_executable)
        self.config_file_exists = self.file_exists_func(self.server_dirs.path_conf_file)
        self.version = self.get_version()

    def __str__(self) -> str:
        return str(self.__dict__)

    def get_executable_path(self)->str:
        return self.server_dirs.path_executable

    def get_executable_path_exists(self) -> bool:
        return os.path.exists(self.server_dirs.path_executable)

    def get_executable_path_does_not_exists_msg(self) -> str:
        return f"spire_executable[{self.server_dirs.path_executable}] does not exits"

    def get_version(self) -> Tuple[Optional[str],Optional[str]]:
        return spire_cmd.get_pire_executable_version(
            executable_path=self.get_executable_path(),
            executable_exists_func= lambda : self.executable_exists,
            executable_path_does_not_exists_msg_func=self.get_executable_path_does_not_exists_msg,
            run_command=self.run_command
        )

    def is_healthy(self) -> Tuple[Optional[bool], Optional[str]]:
        if not self.executable_exists:
            return None, self.get_executable_path_does_not_exists_msg()
        return spire_cmd.is_spire_component_healthy(
            healthcheck_cmd_output_regex=self.re_matching_is_healthy,
            ipc_socket_path_args=spire_cmd.ipc_socket_path_args_server(self.registration_uds_path),
            run_command=self.run_command,
            spire_component_bin=self.server_dirs.path_executable
        )

    def get_trust_domain_id(self) -> Tuple[Optional[str],Optional[str]]:
        agent_svid_der_path = os.path.join(self.server_dirs.data_dir, "bundle.der")
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

    def is_installed(self) -> Tuple[Optional[bool], Optional[str]]:
        actual_version = None if not self.version else self.version[0]
        expected_version_installed = not self.expected_version or self.expected_version == actual_version
        return self.executable_exists and self.config_file_exists and expected_version_installed, None

    def assert_spire_component_and_srv_are_installed(self) -> None:
        res_installed = self.is_installed()
        res_srv_installed = self.is_service_installed()
        if not (res_installed[0] and res_srv_installed[0]):
            raise RuntimeError(
                f"server and its service must be install, but found otherwise: "
                f"server-installed:{res_installed} "
                f", service-installed:{res_srv_installed}"
                f", whoami: {self.run_command.whoami()}"
                f", server_info:{self}"
                )

    def hexdigest_config_file(self) -> Tuple[Optional[str],Optional[str]]:
        if not self.config_file_exists:
            return None, f"config file does not exists: {self.config_file_exists}"
        return digest_hcl_file(self.server_dirs.path_conf_file), None

    def hexdigest_service_file(self) -> Tuple[Optional[str],Optional[str]]:
        if not self.file_exists_func(self.service.service_file):
            return None, f"service file does not exists: {self.service.service_file}"
        return digest_ini_file(self.service.service_file), None


class ServerStateSnapshot:

    def __init__(self, server_info: SpireServerInfo):
        _is_installed = server_info.is_installed()
        self.installed = _is_installed[0]
        self.installed_issue = _is_installed[1]

        _agent_version = server_info.get_version()
        self.version = _agent_version[0]
        self.version_issue = _agent_version[1]

        self.executable_path = server_info.get_executable_path()

        _trust_domain_id = server_info.get_trust_domain_id()
        self.trust_domain_id = _trust_domain_id[0]
        self.trust_domain_id_issue = _trust_domain_id[1]

        _is_service_healthy = server_info.is_healthy()
        self.is_healthy = _is_service_healthy[0]
        self.is_healthy_issue = _is_service_healthy[1]

        _is_service_installed = server_info.is_installed()
        self.service_installed = _is_service_installed[0]
        self.service_installed_issue = _is_service_installed[1]

        _is_service_running =  server_info.is_service_running()
        self.service_running:bool = _is_service_running[0]
        self.service_running_issue:str = _is_service_running[1]

        _is_service__enabled =  server_info.is_service_enabled()
        self.service_enabled: bool = _is_service__enabled[0]
        self.service_enabled_issue = _is_service__enabled[1]

        self.hexdigest_config_file, \
            self.hexdigest_config_file_issue = server_info.hexdigest_config_file()

        self.hexdigest_service_file, \
            self.hexdigest_service_file_issue = server_info.hexdigest_service_file()
        self.service_scope = server_info.service_scope
        self.service_scope_issue = server_info.service_scope_issue

        self.file_stats: FileStats =  server_info.get_local_server_file_stats()

    def get_all_issues(self) -> str:
        all_issues = [
            value
            for key,value in self.__dict__.items()
            if key.endswith("_issue") and value
        ]
        issues_str = "\n".join(all_issues)
        return issues_str or None

    def get_state(self) -> State:
        if self.installed:
            return State.present
        else:
            return State.absent

    def get_state_service_status(self) -> SubStateServiceStatus:
        if self.is_healthy:
            return SubStateServiceStatus.healthy
        elif self.service_running:
            return SubStateServiceStatus.started
        else:
            return SubStateServiceStatus.stopped

    def get_state_service_installation(self) -> SubStateServiceInstallation:
        if self.service_enabled:
            return SubStateServiceInstallation.enabled
        elif self.service_installed:
            return SubStateServiceInstallation.installed
        else:
            return SubStateServiceInstallation.not_installed

    def get_state_of_server(self) -> StateOfServer:
        return StateOfServer(
            state=self.get_state(),
            substate_service_installation=self.get_state_service_installation(),
            substate_service_status=self.get_state_service_status()
        )

    def __get_scope_str(self) -> str:
        if self.service_scope is not None:
            return self.service_scope.scope()
        return None

    def to_ansible_result(self) -> Dict[str, Any]:
        return {
            "spire_server_installed": self.installed,
            "spire_server_installed_issue": self.installed_issue,
            "spire_server_version": self.version,
            "spire_server_version_issue": self.version_issue,
            "spire_server_executable_path": self.executable_path,
            "spire_server_trust_domain_id": self.trust_domain_id,
            "spire_server_trust_domain_id_issue": self.trust_domain_id_issue,
            "spire_server_is_healthy": self.is_healthy,
            "spire_server_is_healthy_issue": self.is_healthy_issue,
            "spire_server_service_scope": self.__get_scope_str(),
            "spire_server_service_scope_issue": self.service_scope_issue,
            "spire_server_service_installed": self.service_installed,
            "spire_server_service_installed_issue": self.service_installed_issue,
            "spire_server_service_running": self.service_running,
            "spire_server_service_running_issue": self.service_running_issue,
            "spire_server_service_enabled": self.service_enabled,
            "spire_server_service_enabled_issue": self.service_enabled_issue,
            "spire_server_hexdigest_service_file": self.hexdigest_service_file,
            "spire_server_hexdigest_service_file_issue": self.hexdigest_service_file_issue,
            "spire_server_hexdigest_config_file": self.hexdigest_config_file,
            "spire_server_hexdigest_config_file_issue": self.hexdigest_config_file_issue,
            "spire_server_file_stats": self.file_stats.to_ansible_result_value()
        }
