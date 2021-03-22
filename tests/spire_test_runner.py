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
import os
import pathlib
import shutil
from string import Template
import subprocess
import tempfile
import textwrap
import time
from typing import Any, Callable, Dict, List, cast

from ansible_collections.io_patricecongo.spire.plugins.module_utils import join_token, systemd
from ansible_collections.io_patricecongo.spire.plugins.module_utils.file_stat import FileModes
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_info_cmd import (
    ServerDirs
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.healthchecks import (
    CheckAgent,
    CheckServer,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    BoolResultWithIssue,
    CmdExecOutcome,
)
from module_utils.logging import get_exception_stacktrace

from . import test_data


def is_project_dir(dir_path: str) -> bool:
    return (bool(dir_path) and dir_path != "/"
            and os.path.exists(os.path.join(dir_path, "galaxy.yml"))
            and os.path.exists(os.path.join(dir_path, "LICENSE")))


def get_project_dir() -> str:
    pjt_dir = os.getcwd()
    while pjt_dir != "/":
        if is_project_dir(pjt_dir):
            return pjt_dir
        pjt_dir = os.path.dirname(pjt_dir)
    msg = f"""Failed to detect project dir(containing galaxy.xml and LICENCE: initial-dir={os.getcwd()}"""
    raise RuntimeError(msg)


def ensure_spire_distribution_is_locally_cached(pjt_dir: str) -> str:
    """ does download the spire distribution if not cached locally using make.
    It returns the path of the cache directory
    """
    make_file = os.path.join(pjt_dir, "molecule/resources/docker-spire-server/Makefile")
    make_cmd_args = ["make", "-f", make_file, "spire-distribution-cached-locally"]
    exec_result: subprocess.CompletedProcess = subprocess.run(make_cmd_args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if exec_result.returncode != 0:
        msg = f"Failed to ensure spire distribution is available locally" \
            f" by using make: {exec_result}"
        raise RuntimeError(msg)
    return os.path.join(pjt_dir, "molecule/resources/docker-spire-server/.download")


def get_free_port() -> int:
    import socketserver
    with socketserver.TCPServer(("localhost", 0), None) as s:
        port = s.server_address[1]
        return port


def join_and_mkdirs(path: str, *paths: str) -> str:
    dir_path = os.path.join(path, *paths)
    #os.makedirs(dir_path, exist_ok=True)
    return dir_path


class DistDownloadDirs:
    def __init__(self, base_dir) -> None:
        if not (base_dir and os.path.exists(base_dir)):
            raise ValueError(f"base-dir({base_dir} must exists")
        self.base_dir = base_dir

    def path_extracted_spire_server_bin(self, spire_version:str) -> str:
        test_data.assert_is_test_version(spire_version)
        return self.find_file_by_subpath_pattern(f"spire-{spire_version}/bin/spire-server")

    def path_extracted_spire_agent_bin(self, spire_version:str) -> str:
        test_data.assert_is_test_version(spire_version)
        return self.find_file_by_subpath_pattern(f"spire-{spire_version}/bin/spire-agent")

    def path_dist_tar_gz(self, spire_version:str) -> str:
        return self.find_file_by_subpath_pattern(f"spire-{spire_version}-linux-*.tar.gz")

    def url_dist_tar_gz(self, spire_version: str) -> str:
        import pathlib
        test_data.assert_is_test_version(spire_version)
        tar_gz_path = pathlib.PurePath(self.path_dist_tar_gz(spire_version))
        return tar_gz_path.as_uri()

    def find_file_by_subpath_pattern(self, sub_path_pattern: str) -> str:
        import glob
        path_pattern = os.path.join(self.base_dir, sub_path_pattern)
        found_files = glob.glob(path_pattern)
        if len(found_files) != 1:
            msg = f"could not find exactly one file for " \
                  f"subpath_pattern({sub_path_pattern}): found={found_files}"
            raise RuntimeError(msg)
        return found_files[0]


class SpireComponentRunner(ABC):

    def __init__(self) -> None:
        self.process: subprocess.Popen = None
        self.project_dir: str = get_project_dir()
        self.dir_spire_distribution_download: str = \
            ensure_spire_distribution_is_locally_cached(pjt_dir=self.project_dir)
        self.__dist_download_dirs: DistDownloadDirs = \
            DistDownloadDirs(base_dir=self.dir_spire_distribution_download)
        #self.__url_dist_tar_gz = self.__dist_download_dirs.url_dist_tar_gz()

    def create_file_from_template(
        self, template_str: str, destination_path: str,
        override_vars: Dict[str, Any] = None
    ) -> None:
        template_config: Template = Template(textwrap.dedent(template_str))
        if override_vars is None:
            override_vars = {}
        all_vars = {**self.__dict__, **override_vars}
        config_str = template_config.substitute(all_vars)
        config_file: pathlib.Path = pathlib.Path(destination_path)
        config_file.write_text(config_str)
        config_file.chmod(0o770)

    @abstractmethod
    def install(self, spire_version: str) -> None:
        pass

    @abstractmethod
    def start(self, must_be_ready: bool = True) -> None:
        pass

    def install_and_start(self, spire_version: str, must_be_ready: bool = True) -> None:
        self.install(spire_version)
        self.start(must_be_ready)

    def dist_download_dirs(self) -> DistDownloadDirs:
        return self.__dist_download_dirs

    def url_dist_tar_gz(self, spire_version) -> str:
        return self.__dist_download_dirs.url_dist_tar_gz(spire_version)



def subprocess_run_command(cmd_parts: Any) -> CmdExecOutcome:
    res: subprocess.CompletedProcess = subprocess.run(
        cmd_parts, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return CmdExecOutcome(
        res.returncode,
        res.stdout.decode(),
        res.stderr.decode())

def chmod(run_command: systemd.CmdExecCallable, mode_to_files: Dict[str,List[str]]) -> None:
    for mode, files in mode_to_files.items():
        for file in files:
            res = run_command(["chmod", mode, file])
            if res.failed():
                raise RuntimeError(f"fail to chmod file: {res}")


class ServerRunner(SpireComponentRunner, CheckServer):

    def __init__(
        self,
        service_name: str,
        scope: systemd.Scope,
        run_command: systemd.CmdExecCallable,
    ) -> None:
        SpireComponentRunner.__init__(self)
        self.base_dir: str = tempfile.mkdtemp(prefix="spire-server-unit-test")
        self.dir_data: str = join_and_mkdirs(self.base_dir, "data")
        self.dir_install: str = join_and_mkdirs(self.base_dir, "install")
        self.dir_install_bin: str = join_and_mkdirs(self.dir_install, "bin")
        self.file_spire_server_bin = os.path.join(self.dir_install_bin, "spire-server")
        self.dir_config: str = join_and_mkdirs(self.base_dir, "conf")
        self.dir_log: str = join_and_mkdirs(self.base_dir, "log")
        self.registration_uds_path = os.path.join(self.base_dir, "spire-registration.sock")
        self.bind_address = "127.0.0.1"
        self.trust_domain = "example.org"
        self.bind_port = get_free_port()
        # self.process: subprocess.Popen = None
        self.readiness_probe_timeout_seconds = 5.0
        self.shutdown_probe_timeout_seconds = 2.5
        self.service = systemd.SpireComponentService(
                                service_name=service_name,
                                run_command=run_command,
                                scope=scope)
        CheckServer.__init__(
            self,
            run_command=run_command, # self.__run_command, # TODO use def subprocess_run_command
            file_spire_server_bin=self.file_spire_server_bin,
            registration_uds_path=self.registration_uds_path,
            readiness_probe_timeout_seconds=5.0
        )
        self.__run_command: systemd.CmdExecCallable = run_command
        self.extra_cleanup_tasks: List[Callable[[], None]] = []

    def get_component_files(self) -> ServerDirs:
        return ServerDirs(
            config_dir=self.dir_config,
            data_dir=self.dir_data,
            install_dir=self.dir_install,
            log_dir=self.dir_log,
            service_dir=self.service.install_dir,
            service_name=self.service.service_name
        )

    def fix_files_modes(self, file_modes: FileModes) -> None:
        files = self.get_component_files()
        chmod(
            run_command=self.__run_command,
            mode_to_files={
                file_modes.mode_dir: files.expected_dirs(),
                file_modes.mode_file_not_exe: files.expected_files_not_exec(),
                file_modes.mode_file_exe: files.expected_files_exec()
            }
        )

    def path_server_config(self) -> str:
        return os.path.join(self.dir_config, "server.conf")

    def __install_server(self, spire_version: str) -> None:
        template_config_str = \
            """\
            server {
                bind_address = "$bind_address"
                #bind_address = "0.0.0.0"
                bind_port = "$bind_port"
                trust_domain = "$trust_domain"
                data_dir = "$dir_data"
                log_level = "DEBUG"
                log_format = "text"
                log_file  = "$dir_log/spire-server.log"
                default_svid_ttl = "48h"
                ca_key_type = "ec-p256"
                ca_ttl = "168h"
                ca_subject {
                    common_name = "unit-test-ca"
                    country = ["de"]
                    organization = ["dev"]
                }
                registration_uds_path = "$registration_uds_path"
                jwt_issuer = "unit-test-ca"
            }

            plugins {
                DataStore "sql" {
                    plugin_data {
                        database_type = "sqlite3"
                        connection_string = "$dir_data/datastore.sqlite3"
                    }
                }
                KeyManager "disk" {
                    plugin_data {
                        keys_path = "$dir_data/keys.json"
                    }
                }
                NodeAttestor "join_token" {
                    plugin_data {}
                }
            }
            """
        # template_config: Template = Template(template_config_str)
        # config_str = template_config.substitute(**self.__dict__)
        # config_file: pathlib.Path = pathlib.Path(self.path_server_config())
        # config_file.write_text(config_str)
        self.create_file_from_template(template_config_str, self.path_server_config())
        shutil.copy2(
            self.dist_download_dirs().path_extracted_spire_server_bin(spire_version),
            self.dir_install_bin
        )

    # TODO move up the hierarchy
    def __make_dir_structure(self) -> None:
        os.makedirs(self.dir_data, exist_ok=True)
        # os.makedirs(self.dir_install, exist_ok=True)
        os.makedirs(self.dir_install_bin, exist_ok=True, mode=0o770)
        os.makedirs(self.dir_config, exist_ok=True, mode=0o770)
        os.makedirs(self.dir_log, exist_ok=True, mode=0o770)

    def path_service_env(self) -> str:
        return os.path.join(self.dir_config, "server.env")

    def __install_service_files(self) -> None:
        template_srv_config_str = \
            """
            ## spire server
            ###############################################################################

            [Unit]
            Description=spire-server
            Documentation=

            [Service]
            Type=simple
            EnvironmentFile=$dir_config/server.env
            ExecStart=$dir_install/bin/spire-server run -expandEnv -config $dir_config/server.conf
            #RemainAfterExit=no
            Restart=on-failure
            RestartSec=5

            [Install]
            WantedBy=multi-user.target
            """
        self.create_file_from_template(
            template_srv_config_str, self.service.service_file)
        template_srv_env_str = """# env  for spire-server service"""
        self.create_file_from_template(template_srv_env_str, self.path_service_env())
        # trust_bundle_file = pathlib.Path(self.dir_config, "trust_bundle.pem")
        # trust_bundle_file.write_text(self.server_bundle)

    def install(self, spire_version: str) -> None:
        self.__make_dir_structure()
        self.__install_server(spire_version)
        self.__install_service_files()

    def start(self, must_be_ready: bool = True) -> None:
        self.service.enable()
        self.service.start()
        if must_be_ready:
            self.wait_for_readiness()

    def register_extra_cleanup_task(self,task: Callable[[],None]):
        if task is not None:
            self.extra_cleanup_tasks.append(task)

    def teardown(self) -> None:
        self.service.teardown_service()
        cleanup_errors: List[Exception] = []
        for ct in self.extra_cleanup_tasks:
            try:
                ct()
            except Exception as e:
                cleanup_errors.append(e)
        if cleanup_errors:
            traces = ",".join(map(get_exception_stacktrace, cleanup_errors))
            msg = f"error while extra_cleanup_tasks: {traces}"
            raise RuntimeError(msg)

    def had_spire_server_been_created(self) -> bool:
        return self.process is not None

    def is_spire_server_process_completed(self) -> bool:
        return self.process is not None and self.process.poll() is not None

    def get_stdout_and_stderr_of_completed_spire_process(self) -> str:
        if self.process is None or not self.is_spire_server_process_completed():
            return None
        return f"""stdout:{self.process.stdout}
                stderr=stdout:{self.process.stderr}
                """

    def wait_for_exit(self, overriding_termination_probe_timeout: float = None) -> BoolResultWithIssue:
        start = time.time()
        termination_probe_timeout_seconds = overriding_termination_probe_timeout
        if termination_probe_timeout_seconds is None:
            termination_probe_timeout_seconds = self.shutdown_probe_timeout_seconds

        def has_not_timeout() -> bool:
            return time.time() - start < termination_probe_timeout_seconds

        res_has_not_timeout = True
        while self.process is not None \
                and self.process.poll() is None \
                and res_has_not_timeout:
            time.sleep(1)
            res_has_not_timeout = has_not_timeout()

        if self.process.poll() is None:
            return BoolResultWithIssue(False, f"exit probe failed:timeout={not res_has_not_timeout}")
        return BoolResultWithIssue(True, None)

    def get_server_bundle(self) -> str:
        generate_token_cmd_args = [
            self.file_spire_server_bin, "bundle", "show",
            "-registrationUDSPath", self.registration_uds_path,
        ]

        res: subprocess.CompletedProcess = subprocess.run(
            generate_token_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to show bundle token: {res}")
        bundle: str = res.stdout.decode()
        return bundle.strip()

    def generate_join_token(self, additional_spiffe_id: str, ttl: int) -> str:
        # ./spire-0.10.x/bin/spire-server token generate -spiffeID spiffe://example.org/myagent1
        def args_contrib_additional_spiffe_id() -> List[str]:
            if additional_spiffe_id is None:
                return []
            return ["-spiffeID", additional_spiffe_id]

        def args_contrib_ttl() -> List[str]:
            return [] if ttl is None else ["-ttl", str(ttl)]

        generate_token_cmd_args = [
            self.file_spire_server_bin, "token", "generate",
            "-registrationUDSPath", self.registration_uds_path,
            *args_contrib_additional_spiffe_id(),
            *args_contrib_ttl()
        ]

        res: subprocess.CompletedProcess = subprocess.run(
            generate_token_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to generate token: {res}")
        extracted = join_token.extract_join_token(res.stdout.decode())
        if extracted is None:
            raise RuntimeError(f"could not extract tken from stdout: stdout={res.stdout}, res={res}")
        return cast(str, extracted)


class AgentRunner(SpireComponentRunner, CheckAgent):
    def __init__(
        self,
        server_address: str, server_port: int,
        socket_path: str,
        service_name: str,
        scope: systemd.Scope,
        run_command: systemd.CmdExecCallable,
    ) -> None:
        SpireComponentRunner.__init__(self)
        self.base_dir: str = tempfile.mkdtemp(prefix="spire-agent-unit-test")
        self.dir_data: str = os.path.join(self.base_dir, "data")
        self.dir_install: str = os.path.join(self.base_dir, "install")
        self.dir_install_bin: str = os.path.join(self.dir_install, "bin")
        self.file_spire_bin = os.path.join(self.dir_install_bin, "spire-agent")
        self.dir_config: str = os.path.join(self.base_dir, "conf")
        self.dir_log: str = os.path.join(self.base_dir, "log")

        self.trust_domain = "example.org"
        self.socket_path = socket_path
        self.server_address: str = server_address
        self.server_port: int = server_port
        self.additional_spiffe_id: str = "spiffe://example.org/agent/local1"
        self.join_token_ttl: int = 600

        self.process: subprocess.Popen = None
        self.readiness_probe_timeout_seconds = 5.0
        self.shutdown_probe_timeout_seconds = 2.5
        self.spire_agent_join_token: str = None
        self.server_bundle: str = None

        self.service = systemd.SpireComponentService(
                                service_name, run_command, scope)
        CheckAgent.__init__(
            self,
            run_command=run_command,
            file_spire_agent_bin=self.file_spire_bin,
            socket_path=socket_path,
            readiness_probe_timeout_seconds=10.0
        )

    def path_config(self) -> str:
        return os.path.join(self.dir_config, "agent.conf")

    def path_service_env(self) -> str:
        return os.path.join(self.dir_config, "agent.env")

    # TODO move up the hierarchy
    def __make_dir_structure(self) -> None:
        os.makedirs(self.dir_data, exist_ok=True)
        # os.makedirs(self.dir_install, exist_ok=True)
        os.makedirs(self.dir_install_bin, exist_ok=True, mode=0o770)
        os.makedirs(self.dir_config, exist_ok=True, mode=0o770)
        os.makedirs(self.dir_log, exist_ok=True, mode=0o770)

    def __install_agent(self, spire_version: str) -> None:
        template_config_str = \
            """\
            agent {
                data_dir = "$dir_data"
                log_level = "DEBUG"
                log_file  = "$dir_log/spire-agent.log"
                trust_domain = "$trust_domain"
                server_address = "$server_address"
                server_port = $server_port
                socket_path ="$socket_path"
                insecure_bootstrap = false
                trust_bundle_path = "$dir_config/trust_bundle.pem"
                join_token = "$spire_agent_join_token"
            }

            plugins {
                KeyManager "disk" {
                    plugin_data {
                        directory = "$dir_data"
                    }
                }

                NodeAttestor "join_token" {
                    plugin_data {}
                }

                WorkloadAttestor "unix" {
                    plugin_data {}
                }
            }
            """
        self.create_file_from_template(template_config_str, self.path_config())
        shutil.copy2(
            self.dist_download_dirs().path_extracted_spire_agent_bin(spire_version),
            self.dir_install_bin
        )

    def __install_service_files(self) -> None:
        template_srv_config_str = \
            """\
            ## spire agent
            ###############################################################################

            [Unit]
            Description=spire-agent
            Documentation=

            [Service]
            Type=simple
            EnvironmentFile=$dir_config/agent.env
            ExecStart=$dir_install/bin/spire-agent run -expandEnv -config $dir_config/agent.conf
            #RemainAfterExit=no
            Restart=on-failure
            RestartSec=5

            [Install]
            WantedBy=multi-user.target
            """
        self.create_file_from_template(
            template_srv_config_str, self.service.service_file)
        template_srv_env_str = """spire_agent_join_token='$spire_agent_join_token'"""
        self.create_file_from_template(template_srv_env_str, self.path_service_env())
        trust_bundle_file = pathlib.Path(self.dir_config, "trust_bundle.pem")
        trust_bundle_file.write_text(self.server_bundle)

    def install(self, spire_version: str) -> None:
        self.__make_dir_structure()
        self.__install_agent(spire_version)
        self.__install_service_files()

    def start(self, must_be_ready: bool = True) -> None:
        self.service.enable()
        self.service.start()
        if must_be_ready:
            self.wait_for_readiness()

    def teardown(self) -> None:
        self.service.teardown_service()

    def had_process_been_created(self) -> bool:
        return self.process is not None

    def is_process_completed(self) -> bool:
        return self.process is not None and self.process.poll() is not None

    def get_stdout_and_stderr_of_completed_spire_process(self) -> str:
        if self.process is None or not self.is_process_completed():
            return None
        return f"""stdout:{self.process.stdout}
                stderr=stdout:{self.process.stderr}
                """

    def wait_for_exit(self, overriding_termination_probe_timeout: float = None) -> BoolResultWithIssue:
        start = time.time()
        termination_probe_timeout_seconds = overriding_termination_probe_timeout
        if termination_probe_timeout_seconds is None:
            termination_probe_timeout_seconds = self.shutdown_probe_timeout_seconds

        def has_not_timeout() -> bool:
            return time.time() - start < termination_probe_timeout_seconds

        res_has_not_timeout = True
        while self.process is not None \
                and self.process.poll() is None \
                and res_has_not_timeout:
            time.sleep(1)
            res_has_not_timeout = has_not_timeout()

        if self.process.poll() is None:
            msg = f"exit probe failed:timeout={not res_has_not_timeout}"
            return BoolResultWithIssue(False, msg)
        return BoolResultWithIssue(True, None)
