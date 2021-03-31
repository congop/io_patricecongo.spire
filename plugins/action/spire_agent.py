#!/usr/bin/python
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

# Make coding more python3-ish, this is required for contributions to Ansible
from datetime import datetime, timezone
import os
import time
from typing import Any, Callable, Dict, List, Union, cast

from ansible.parsing import dataloader
from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task
from ansible.plugins import loader as plugins_loader
from ansible.plugins.connection.__init__ import ConnectionBase
from ansible.template import Templar
from ansible_collections.io_patricecongo.spire.plugins.module_utils import join_token, logging
from ansible_collections.io_patricecongo.spire.plugins.module_utils.agent_templates.resources import (
    AgentTemplates,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.diffs import (
    DigestDiff,
    StrResourceDiff,
    VersionDiff,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.digests import (
    digest_hcl_file,
    digest_ini_file,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.file_stat import (
    ExpectedStatsByMode,
    FileModes,
    FileStats,
    FileStatsDiff,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.module_outcome import (
    assert_shell_or_cmd_task_successful,
    assert_task_did_not_failed,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_action_base import (
    DiffSpireCmptActualExpected,
    SpireActionBase,
    SpireCmptInfoResultAdapter,
    SpireTemplateRes,
    make_local_temp_work_dir,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_info_cmd import (
    AgentDirs,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_registration_info_cmd import (
    AgentRegistrationEntry,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    State,
    StateOfAgent,
    StateOfAgentDiff,
    SubStateAgentRegistered,
    SubStateServiceStatus,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.systemd import Scope
from ansible_collections.io_patricecongo.spire.plugins.module_utils.tar_utils import (
    extract_tar_member,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.users import User


class AgentRegistrationInfoResultAdapter:
    def __init__(self, result: Dict[str, Any]) -> None:
        if result is None:
            result = {}
        self.result = result
        registration_data = result.get("spire_agent_registrations")
        if registration_data is None:
            registration_data = []
        self.registrations: List[AgentRegistrationEntry] = [
            AgentRegistrationEntry.from_ansible_result_registration_entry(e)
            for e in registration_data
        ]

    def select_matching_registration(self,
                                     spiffe_id: str,
                                     attestation_type: str,
                                     serial_number: int
                                     ) -> List[AgentRegistrationEntry]:

        def matches_criteria(entry: AgentRegistrationEntry) -> bool:
            return bool(
                spiffe_id == entry.spiffe_id
                and attestation_type == entry.attestation_type
                and serial_number == entry.serial_number
            )

        return [e for e in self.registrations if matches_criteria(e)]


class AgentInfoResultAdapter(SpireCmptInfoResultAdapter):

    def __init__(self, result: Dict[str, Any]) -> None:
        if result is None:
            result = {}
        super().__init__(
            result = result or {},
            installed=result.get("spire_agent_installed", "False"),
            version=result.get("spire_agent_version"),
            version_issue=result.get("spire_agent_version_issue"),
            executable_path=result.get("spire_agent_executable_path"),
            trust_domain_id=result.get("spire_agent_trust_domain_id"),
            trust_domain_id_issue=result.get("spire_agent_trust_domain_id_issue"),
            is_healthy=result.get("spire_agent_is_healthy", False),
            is_healthy_issue=result.get("spire_agent_is_healthy_issue"),
            service_scope=Scope.by_name(result.get("spire_agent_service_scope")),
            service_scope_issue=result.get("spire_agent_service_scope_issue"),
            service_installed=result.get("spire_agent_service_installed", False),
            service_installed_issue=result.get("spire_agent_service_installed_issue"),
            service_running=result.get("spire_agent_service_running", False),
            service_running_issue=result.get("spire_agent_service_running_issue"),
            service_enabled=result.get("spire_agent_service_enabled", False),
            service_enabled_issue=result.get("spire_agent_service_enabled_issue"),
            hexdigest_service_file=result.get("spire_agent_hexdigest_service_file"),
            hexdigest_service_file_issue=result.get("spire_agent_hexdigest_service_file_issue"),
            hexdigest_config_file=result.get("spire_agent_hexdigest_config_file"),
            hexdigest_config_file_issue=result.get("spire_agent_hexdigest_config_file_issue"),
            file_stats=FileStats.from_ansible_result(result, "spire_agent_file_stats")
        )
        self.spiffe_id=result.get("spire_agent_spiffe_id")
        self.serial_number: str = result.get("spire_agent_serial_number")
        self.spiffe_id_issue: str = result.get("spire_agent_spiffe_id_issue")
        self.is_registered: bool = False

    def spire_agent_serial_number_as_int(self) -> int:
        '''Return the serial number as interger  or -1 if no value is avalaible yet'''
        if self.serial_number:
            return int(self.serial_number)
        return None

    def __get_state_registered(self) -> SubStateAgentRegistered:
        if self.is_registered:
            return SubStateAgentRegistered.yes
        else:
            return SubStateAgentRegistered.no

    def to_detected_state(self) -> StateOfAgent:
        return StateOfAgent(
            state=self._get_state(),
            substate_agent_registered=self.__get_state_registered(),
            substate_service_installation=self._get_state_service_installation(),
            substate_service_status=self._get_state_service_status()
        )

    def to_ansible_return_data(self) -> Dict[str, Union[str, bool, Dict[str, Any]]]:
        state_data = self.to_detected_state().to_ansible_return_data()
        return {**state_data,
                "actual_spire_agent_version": self.version,
                "actual_spire_agent_serial_number": self.serial_number,
                "actual_spire_agent_spiffe_id": self.spiffe_id,
                "actual_spire_agent_trust_domain_id": self.trust_domain_id,
                "actual_spire_agent_executable_path": self.executable_path,
                "actual_spire_agent_get_info_issue": self._get_issues_issues(),
                "actual_spire_agent_get_info_result": self.result
                }


class AgentActionData:
    def __init__(self) -> None:
        self.local_temp_work_dir: str = None
        self.templates: AgentTemplates = None
        self.join_token: str = None
        self.spire_server_bundle: str = None
        self.spire_agent_info: AgentInfoResultAdapter = AgentInfoResultAdapter({})
        self.spire_server_version: str = None
        self.downloaded_dist_path: str = None
        self.expected_state: StateOfAgent = None
        self.dirs: AgentDirs = None
        self.expected_file_modes: FileModes = None
        self.expected_file_modes_effective: FileModes = None
        self.agent_service_return: Dict[str, Any] = None
        self.expected_config: ExpectedConfig = None
        self.expected_stats_by_mode: ExpectedStatsByMode = None
        self.expected_file_stats: FileStats = None
        self.expected_user: User = None

    def need_change(self) -> bool:
        actual_state = self.spire_agent_info.to_detected_state()
        return bool(actual_state.need_change(self.expected_state))

    def to_ansible_return_data(self) -> Dict[str, Any]:
        actual_state_result_data = self.spire_agent_info.to_ansible_return_data()
        return {**actual_state_result_data}

    def to_ansible_retun_data_failed_entry(self) -> Dict[str, bool]:
        if not self.need_change():
            return {}
        return {"failed": True}

    def diff(self) -> DiffSpireCmptActualExpected:
        # TODO move resource(uri) into diff (when executable has moved? how to model that)
        #info = self.spire_server_info

        expected: ExpectedConfig = self.expected_config
        actual: AgentInfoResultAdapter = self.spire_agent_info
        dirs: AgentDirs = self.dirs
        file_stats_diff = FileStatsDiff.for_files(
            files=dirs.expected_dirs_and_files(),
            file_stats_actual=actual.file_stats,
            file_stats_expected=self.expected_file_stats,
            system_dirs={
                    "/etc/systemd/system",
                    "/var/log"
            },
            user_system_dirs=set(
                self.expected_user.system_dirs()
            )
        )
        # file_stats_diff.
        exe_versions = [
            VersionDiff(
                resource_id=dirs.path_executable,
                version_actual=actual.version,
                version_expected=expected.spire_version
            )
        ]
        state_diff = StateOfAgentDiff(
            actual=actual.to_detected_state(),
            expected=self.expected_state
        )
        # "Faking" env-file digest
        # Using existence to make sure it will be created.
        # ==>Update not covered
        # TODO: do real diff
        #       env is bash file or really just  ini?
        env_file = dirs.path_env_file
        env_file_digest_diff = DigestDiff(
            file=env_file,
            digest_actual=f"exists={actual.file_stats.exists(env_file)}",
            digest_expected=f"exists={self.expected_file_stats.exists(env_file)}"
        )

        # TODO do real bundle content diff
        bundle_file = dirs.path_trust_bundle_pem
        bundle_file_digest_diff = DigestDiff(
            file=bundle_file,
            digest_actual=f"exists={actual.file_stats.exists(bundle_file)}",
            digest_expected=f"exists={self.expected_file_stats.exists(bundle_file)}"
        )

        file_contents: List[DigestDiff] = [
            DigestDiff(
                file=dirs.path_conf_file,
                digest_actual=actual.hexdigest_config_file,
                digest_expected=expected.config_file_digest
            ),
            DigestDiff(
                file=dirs.path_service_file,
                digest_actual=actual.hexdigest_service_file,
                digest_expected=expected.service_file_disgest
            ),
            env_file_digest_diff,
            bundle_file_digest_diff
        ]
        scope_diff = StrResourceDiff(
            resource_id="spire-server-service-scope",
            actual=Scope.noneOrScope(actual.service_scope),
            expected=Scope.noneOrScope(expected.service_scope)
        )
        diff = DiffSpireCmptActualExpected(
            scope_diff=scope_diff,
            exe_versions=exe_versions,
            file_attrs=list(file_stats_diff.file_stat_diffs.values()),
            file_contents=file_contents,
            state_diff=state_diff,
        )
        return diff


class ExpectedConfig:

    def __init__(
        self,
        exe_template_on_localhost: Callable[[SpireTemplateRes], str],
        templates: AgentTemplates,
        expected_state: State,
        expected_spire_version: str,
        expected_service_scope: Scope,
        spire_server_bundle: str,
        join_token: str,
        task_args: Dict[str, Any]
    ):
        self.env_file: str = None
        self.service_file: str = None
        self.conf_file: str = None
        self.trust_bundle_file: str = None
        self.service_file_disgest: str = None
        self.config_file_digest: str = None
        self.spire_version: str = None
        self.service_scope: Scope = None

        if expected_state == State.present:
            self.service_scope = expected_service_scope
            self.spire_version = expected_spire_version
            #server_templates: ServerTemplates = action_data.server_templates
            #extra_vars_service_env: Dict[str, str] = {}
            extra_vars_service_env: Dict[str, str] = {"spire_agent_join_token": join_token}
            # TODO join-toen is just for creating if agent is running we want
            # to ignore hashes of file containing it, we do want to avoid creating it when not necesarry
            # is test present enough?
            template_resources = [
                SpireTemplateRes(
                    label="service.env", src=templates.tmpl_service_env,
                    extra_vars=extra_vars_service_env),
                SpireTemplateRes(
                    label="service", src=templates.tmpl_service,
                    extra_vars={**task_args}),
                SpireTemplateRes(
                    label="conf", src=templates.tmpl_conf,
                    extra_vars={**task_args}),
                SpireTemplateRes(
                    label="server_bundle",
                    src=templates.tmpl_server_bundle,
                extra_vars={**task_args, "spire_server_bundle": spire_server_bundle}
            )
            ]
            self.env_file, self.service_file, self.conf_file, self.trust_bundle_file = [
                exe_template_on_localhost(tres) for tres in template_resources]
            self.service_file_disgest = digest_ini_file(self.service_file)
            self.config_file_digest = digest_hcl_file(self.conf_file)


class ActionModule(SpireActionBase):

    def __init__(
        self, task: Task, connection: ConnectionBase,
        play_context: PlayContext, loader: dataloader.DataLoader,
        templar: Templar, shared_loader_obj: plugins_loader
    ) -> None:
        super().__init__(
            task=task, connection=connection, play_context=play_context,
            loader=loader, templar=templar,
            shared_loader_obj=shared_loader_obj,
            module_fq_name="io_patricecongo.spire.spire_agent")
        self.action_data: AgentActionData = AgentActionData()
        # self.diff_actual_expected: DiffSpireCmptActualExpected = None

    def _get_spire_server(self) -> str:
        return "spire_server"

    def _ensure_dir_structure_and_binary_available(
            self, task_vars: Dict[str, Any] = None
    ) -> None:
        file_modes = self.action_data.expected_file_modes_effective
        downloaded_spire_dist_path = self.action_data.downloaded_dist_path
        dirs: AgentDirs = self.action_data.dirs
        expected_dirs = dirs.expected_dirs()
        dirs_needing_change: List[str] = self.diff_actual_expected.dirs_needing_change(expected_dirs)
        self._create_remote_dirs(
            task_vars=task_vars,
            expected_dirs=dirs_needing_change,
            mode=file_modes.mode_dir
        )

        if  not self.need_spire_binary_change():
            return

        spire_server_binary_extracted_path = extract_tar_member(
            downloaded_spire_dist_path,
            "/bin/spire-agent")

        self._copy_from_controller_to_target(
            copy_task_label=f"spire-agent({spire_server_binary_extracted_path})",
            src=spire_server_binary_extracted_path,
            dest=dirs.install_dir_bin,
            sec_attributes={
                "owner": self.get_install_file_owner(),
                "mode": file_modes.mode_file_exe
            },
            task_vars=task_vars,
        )
        return

    def _get_current_spire_agent_host(self, task_vars: Dict[str, Any]) -> str:
        return cast(str, task_vars['inventory_hostname'])

    def _get_service_scope_str(self) -> str:
        return cast(str, self._task.args.get("spire_agent_service_scope"))

    def _get_expected_service_scope(self) -> Scope:
         scope_str = self._get_service_scope_str()
         if scope_str:
            return Scope.by_name(scope_str)
         return Scope.scope_system

    def get_expected_version(self) -> str:
        return cast(str, self._task.args.get("spire_agent_version"))

    def __ensure_expected_config_available_locally(
                self, task_vars: Dict[str, Any] = None,
        ) -> None:
            action_data = self.action_data

            expected_state = StateOfAgent.from_task_args(self._task.args)
            action_data.expected_state = expected_state

            action_data.expected_user = self.remote_user_data()

            file_modes = FileModes.from_dict(
                data=self._task.args,
                mapping= {
                    "mode_dir": "spire_agent_install_dir_mode",
                    "mode_file_not_exe": "spire_agent_install_file_mode",
                    "mode_file_exe": "spire_agent_install_file_mode_exe"
                }
            )
            action_data.expected_file_modes = file_modes

            state = expected_state.state
            action_data.expected_config = ExpectedConfig(
                exe_template_on_localhost=self._exe_template_on_localhost,
                templates=action_data.templates,
                expected_state=state,
                expected_spire_version=self.get_expected_version(),
                expected_service_scope=self._get_expected_service_scope(),
                task_args=self._task.args,
                spire_server_bundle=self._get_spire_server_bundle(), # action_data.spire_server_bundle,
                join_token=self._get_join_token() # TODO onyl if we are going to need it
            )

            if state == State.present:
                expected_stats_by_mode_builder = ExpectedStatsByMode.assuming_present
            else:
                expected_stats_by_mode_builder = ExpectedStatsByMode.assuming_absent

            #file_modes = action_data.expected_file_modes
            expected_stats_by_mode = expected_stats_by_mode_builder(
                dir_modes = [
                    file_modes.mode_dir
                ],
                file_modes = [
                    file_modes.mode_file_not_exe,
                    file_modes.mode_file_exe
                ],
                task_vars= task_vars,
                file_access=self
            )
            file_modes_effective = expected_stats_by_mode.effective_modes(file_modes)
            action_data.expected_file_modes_effective = file_modes_effective
            action_data.expected_stats_by_mode = expected_stats_by_mode
            dirs = action_data.dirs
            action_data.expected_file_stats = expected_stats_by_mode.expected_file_stats(
                mode_to_dir= dirs.mode_to_expected_dirs(file_modes),
                mode_to_file=dirs.mode_to_expected_files(file_modes)
            )
            return

    def get_install_file_owner(self) -> str:
        owner: str = self._get_str_from_original_task_args("spire_agent_install_file_owner")
        return owner

    def _ensure_service_files_installed(
            self, task_vars: Dict[str, Any] = None,
    ) -> None:
        diff: DiffSpireCmptActualExpected = self.diff_actual_expected
        action_data = self.action_data
        config: ExpectedConfig = action_data.expected_config

        # TODO sec attribute for each file at least executable vs config vs secrets
        sec_attributes = {
            "owner": self.get_install_file_owner(),
            "mode": action_data.expected_file_modes_effective.mode_file_not_exe
        }
        dirs: AgentDirs = action_data.dirs

        #(label,source,destination)
        copy_task_specs =[
            ("agent.env", config.env_file, dirs.path_env_file),
            ("agent.conf", config.conf_file, dirs.path_conf_file),
            ("agent_server.service", config.service_file, dirs.path_service_file),
            ("trust-bundle.pem", config.trust_bundle_file, dirs.path_trust_bundle_pem)
        ]
        for label, src, dest in copy_task_specs:
            if diff.need_content_change(dest):
                self._copy_from_controller_to_target(
                    task_vars=task_vars, copy_task_label=label,
                    src=src, dest=dest,
                    sec_attributes=sec_attributes.copy())
            elif diff.need_attrs_change(dest):
                self.create_remote_file(
                    file_path=dest,
                    mode=None,
                    state="file",
                    task_vars=task_vars,
                    module_args_overrides=sec_attributes.copy(),
                )

    def _wait_for_spire_agent_healthy(self, task_vars: Dict[str, Any] = None) -> None:
        def found_that_agent_is_healthy() -> bool:
            info = self.action_data.spire_agent_info
            is_healthy: bool = info.is_healthy
            return is_healthy

        self._get_spire_agent_info(task_vars=task_vars, with_registration_check=False)
        timeout = self._get_float_from_original_task_args("spire_agent_healthiness_probe_timeout_seconds")
        if timeout is None:
            return
        start = time.time()
        while not found_that_agent_is_healthy() and (time.time() - start) < timeout:
            time.sleep(1)
            self._get_spire_agent_info(task_vars=task_vars)

    def get_registration_uds_path_server_cmd_args_contribution(self) -> List[str]:
        uds_path = self._get_str_from_original_task_args("spire_server_registration_uds_path")
        if not uds_path:
            return []
        return ["-registrationUDSPath", uds_path]

    def _run_spire_server_cmd_sub_task(
            self,
            task_vars: Dict[str, Any] = None,
            spire_server_cmd_args: List[str] = None,
            task_cmd_label: str = None,
            add_uds_path_arg: bool = True
    ) -> Dict[str, Any]:
        spire_server_host = self._get_str_from_original_task_args("spire_server_host")
        if not spire_server_host:
            original_task_args_key = self._get_original_task_args_key()
            raise RuntimeError(
                f"spire_server_host must be specified: "
                f"value={spire_server_host} "
                f"task-args-keys={original_task_args_key}")

        spire_server_install_dir = self._get_str_from_original_task_args("spire_server_install_dir")
        cmd_spire_server = "spire-server"
        if spire_server_install_dir:
            cmd_spire_server = os.path.join(spire_server_install_dir, "bin", "spire-server")
            cmd_spire_server = os.path.normpath(cmd_spire_server)
        uds_path_addition = self.get_registration_uds_path_server_cmd_args_contribution() if add_uds_path_arg else []
        module_args = {
            "argv": [cmd_spire_server, *spire_server_cmd_args, *uds_path_addition]
        }

        data = {
            "name": f"{self._task.get_name()}-command-spire-server-{task_cmd_label or ''}",
            "command": module_args,
        }

        version_ret: Dict[str, Any] = self._run_sub_task(task_data=data, hostname=spire_server_host)

        return version_ret

    def _get_spire_server_version(self, task_vars: Dict[str, Any] = None) -> None:
        version_ret = self._run_spire_server_cmd_sub_task(
            task_vars=task_vars,
            task_cmd_label="version",
            spire_server_cmd_args=["--version"],
            add_uds_path_arg=False)
        spire_server_host = self._get_str_from_original_task_args("spire_server_host")
        assert_shell_or_cmd_task_successful(
            version_ret,
            f"Fail to get spire-server version on [{spire_server_host}]")
        stdout = version_ret.get("stdout")
        stderr = version_ret.get("stderr")
        self.action_data.spire_server_version = stderr or stdout

    def _get_spire_server_bundle(self, task_vars: Dict[str, Any] = None) -> str:
        if self.action_data.spire_server_bundle is None:
            # /opt/spire/bin/spire-server bundle show > nestedB/agent/bootstrap.crt
            version_ret = self._run_spire_server_cmd_sub_task(
                task_vars=task_vars,
                task_cmd_label="bundle show",
                spire_server_cmd_args=["bundle", "show"])

            assert_shell_or_cmd_task_successful(version_ret, "Fail to get spire-server bundle show")
            stdout = cast(str, version_ret.get("stdout"))
            self.action_data.spire_server_bundle = stdout
        return self.action_data.spire_server_bundle

    def _get_join_token(self, task_vars: Dict[str, Any] = None) -> str:

        def args_contrib_ttl() -> List[str]:
            ttl = self._get_int_from_original_task_args("spire_agent_join_token_ttl")
            if ttl is None or str(ttl).isspace():
                # ttl actually an number, so using <if ttl> is not the same as <if specified> because ttl=0 is false
                return []
            return ["-ttl", str(ttl)]

        def args_contrib_additional_spiffe_id() -> List[str]:
            spire_agent_additional_spiffe_id = self._get_str_from_original_task_args("spire_agent_additional_spiffe_id")
            if spire_agent_additional_spiffe_id is None or str(spire_agent_additional_spiffe_id).isspace():
                return []
            return ["-spiffeID", spire_agent_additional_spiffe_id]

            # ./spire-0.10.x/bin/spire-server token generate -spiffeID spiffe://example.org/myagent1
        if self.action_data.join_token is None:
            spire_server_cmd_args = [
                "token", "generate", *args_contrib_additional_spiffe_id(), *args_contrib_ttl()
            ]

            version_ret = self._run_spire_server_cmd_sub_task(
                task_vars=task_vars,
                task_cmd_label="token generate",
                spire_server_cmd_args=spire_server_cmd_args)

            assert_shell_or_cmd_task_successful(version_ret, "Fail to get spire-server token generate")

            token_stdout = version_ret.get("stdout")
            jointoken: str = join_token.extract_join_token(token_stdout)
            if not jointoken:
                msg = f"""Bad token generate stdout format
                    token_stdout={token_stdout}
                """
                raise RuntimeError(msg)
            self.action_data.join_token = jointoken
        return self.action_data.join_token

    def _get_original_task_args_key(self) -> List[str]:
        return [*self._task.args]

    def _get_spire_agent_info(
            self, task_vars: Dict[str, Any] = None,
            with_registration_check: bool = True
    ) -> None:
        original_task_args = self._task.args
        service_scope = self._get_service_scope_str()
        dirs: AgentDirs = self.action_data.dirs
        module_args = {
            "spire_agent_config_dir": dirs.config_dir,
            "spire_agent_data_dir": dirs.data_dir,
            "spire_agent_install_dir": dirs.install_dir,
            "spire_agent_log_dir": dirs.log_dir,
            "spire_agent_service_dir": dirs.service_dir,
            "spire_agent_socket_path":
                self._get_str_from_original_task_args("spire_agent_socket_path"),
            "spire_agent_service_name": dirs.service_full_name,
            "spire_agent_service_scope": service_scope
        }

        cmd_task_vars = task_vars.copy()
        # 'io_patricecongo.spire.plugins.modules.spire_agent_info',#
        module_ret = self._execute_module(
            module_name='io_patricecongo.spire.spire_agent_info',
            module_args=module_args,
            task_vars=cmd_task_vars, tmp=None)

        assert_task_did_not_failed(
            task_ret=module_ret,
            msg_label="fail to io_patricecongo.spire.spire_agent_info:"
        )

        agent_info = AgentInfoResultAdapter(module_ret)
        self.action_data.spire_agent_info = agent_info
        if with_registration_check:
            registration_info = self._get_spire_agent_registration_info(agent_info)
            matching_registration: List[AgentRegistrationEntry] = \
                registration_info.select_matching_registration(
                    spiffe_id=agent_info.spiffe_id,
                    attestation_type="join_token",
                    serial_number=agent_info.spire_agent_serial_number_as_int()
                )
            now = datetime.now(timezone.utc)

            def has_not_expired(e: object) -> bool:
                return bool(cast(AgentRegistrationEntry, e).expiration_time > now)

            agent_info.is_registered = any(filter(has_not_expired, matching_registration))
        return

    def _get_spire_agent_registration_info(
            self, agent_info: AgentInfoResultAdapter
    ) -> AgentRegistrationInfoResultAdapter:
        if not agent_info.spiffe_id:
            return AgentRegistrationInfoResultAdapter({})

        spire_server_install_dir = self._get_str_from_original_task_args("spire_server_install_dir")
        uds_path = self._get_str_from_original_task_args("spire_server_registration_uds_path")
        dirs: AgentDirs = self.action_data.dirs
        module_args = {
            "spire_agent_spiffe_id": agent_info.spiffe_id,
            "spire_server_install_dir": spire_server_install_dir,
            "spire_server_registration_uds_path": uds_path
        }

        spire_server_host = self._get_str_from_original_task_args("spire_server_host")
        if not spire_server_host:
            original_task_args_key = self._get_original_task_args_key()
            msg = f"""spire_server_host must be specified:
                        value={spire_server_host}
                        task-args-keys={original_task_args_key}
                    """
            raise RuntimeError(msg)

        data = {
            "name": f"{self._task.get_name()}-get-agent-registration",
            "io_patricecongo.spire.spire_agent_registration_info": module_args,
        }

        registration_ret = self._run_sub_task(task_data=data, hostname=spire_server_host)

        return AgentRegistrationInfoResultAdapter(registration_ret)

    def __service_state_to_stopped(self, task_args: Dict[str, Any]) -> Dict[str, Any]:
        info = self.get_info()
        return {
            **task_args,
            "substate_service_status": SubStateServiceStatus.stopped.name,
            "spire_agent_version": info.version
        }

    def get_info(self) -> SpireCmptInfoResultAdapter:
        return self.action_data.spire_agent_info

    def need_spire_binary_change(self) -> bool:
        need_change: bool = self.diff_actual_expected.need_binary_change(
            bin_file=self.action_data.dirs.path_executable
        )
        return need_change

    def run(
        self, tmp: Any = None, task_vars: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        super(ActionModule, self).run(tmp, task_vars)

        tv = dict(task_vars)
        changed = False
        failed_contrib: Dict[str, Any] = {}
        try:
            self.action_data.templates = AgentTemplates()
            self.action_data.local_temp_work_dir = make_local_temp_work_dir("spire-agent-work-dir")
            self.action_data.dirs = AgentDirs.from_ansible_src(self._get_str_from_original_task_args)
            self.__ensure_expected_config_available_locally(task_vars=tv)

            self._get_spire_agent_info(task_vars=tv)
            self.diff_actual_expected = self.action_data.diff()

            if self.get_check_mode():
                cm_ret: Dict[str, Any] = self.check_mode_ansible_return()
                return cm_ret

            if self.diff_actual_expected.need_change():
                changed = True
                if State.present == self.action_data.expected_state.state:
                    self.stop_spire_cmpt_service_if_running(
                        task_args_mapper=self.__service_state_to_stopped,
                        task_vars=tv)
                    self._get_join_token(task_vars=tv)
                    self._get_spire_server_bundle()
                    self._get_spire_server_version(task_vars=tv)
                    self.action_data.downloaded_dist_path = self._download_spire_release(
                        download_decider=self.need_spire_binary_change
                    )
                    self._ensure_dir_structure_and_binary_available(task_vars=tv)
                    self._ensure_service_files_installed(task_vars=tv)
                self._execute_actual_spire_ansible_module(task_vars=tv)
                self._get_spire_agent_info(task_vars=tv)
                diff_after_change: DiffSpireCmptActualExpected = self.action_data.diff()
                failed_contrib = diff_after_change.ansible_failed_outcome_part_given_no_diff_expected()
        except Exception as e:
            msg = f"""Error while running spire-agent action:
                    message:{str(e)}
                    stacktrace: {logging.get_exception_stacktrace(e)}
                    action_data : {self.action_data}
                    """
            self._display.v(msg)
            raise e
        else:
            ret = {
                'changed': changed,
                **self.action_data.to_ansible_retun_data_failed_entry(),
                **failed_contrib,
                **self.diff_actual_expected.ansible_diff_outcome_part(
                        diff_activated=self.get_diff_mode()
                ),
                **self.action_data.to_ansible_return_data()
            }
            return ret
