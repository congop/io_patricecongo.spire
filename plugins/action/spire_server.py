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
import shutil
from typing import Any, Callable, Dict, List, Union, cast

from ansible.parsing import dataloader
from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task
from ansible.plugins import loader as plugins_loader
from ansible.plugins.connection.__init__ import ConnectionBase
from ansible.template import Templar
from ansible_collections.io_patricecongo.spire.plugins.module_utils import logging
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
    assert_task_did_not_failed,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.server_templates.resources import (
    ServerTemplates,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_action_base import (
    DiffSpireCmptActualExpected,
    SpireActionBase,
    SpireTemplateRes,
    make_local_temp_work_dir,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_info_cmd import (
    ServerDirs,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    State,
    StateOfServer,
    StateOfServerDiff,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.systemd import Scope
from ansible_collections.io_patricecongo.spire.plugins.module_utils.tar_utils import (
    extract_tar_member,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.users import User


class ServerInfoResultAdapter:
    def __init__(self, result: Dict[str, Any]) -> None:
        result = result or {}
        self.result = result or {}
        self.spire_server_installed: bool = result.get("spire_server_installed", "False")
        self.spire_server_version: str = result.get("spire_server_version")
        self.spire_server_version_issue: str = result.get("spire_server_version_issue")
        self.spire_server_executable_path: str = result.get("spire_server_executable_path")
        self.spire_server_trust_domain_id: bool = result.get("spire_server_trust_domain_id")
        self.spire_server_trust_domain_id_issue: str = result.get("spire_server_trust_domain_id_issue")
        self.spire_server_is_healthy: bool = result.get("spire_server_is_healthy", False)
        self.spire_server_is_healthy_issue: str = result.get("spire_server_is_healthy_issue")
        self.spire_server_service_scope: Scope = Scope.by_name( result.get("spire_server_service_scope") )
        self.spire_server_service_scope_issue: str = result.get("spire_server_service_scope_issue")
        self.spire_server_service_installed: bool = result.get("spire_server_service_installed", False)
        self.spire_server_service_installed_issue: str = result.get("spire_server_service_installed_issue")
        self.spire_server_service_running: bool = result.get("spire_server_service_running", False)
        self.spire_server_service_running_issue: str = result.get("spire_server_service_running_issue")
        self.spire_server_service_enabled: bool = result.get("spire_server_service_enabled", False)
        self.spire_server_service_enabled_issue: str = result.get("spire_server_service_enabled_issue")
        self.hexdigest_service_file = result.get("spire_server_hexdigest_service_file")
        self.hexdigest_service_file_issue = result.get("spire_server_hexdigest_service_file_issue")
        self.hexdigest_config_file = result.get("spire_server_hexdigest_config_file")
        self.hexdigest_config_file_issue = result.get("spire_server_hexdigest_config_file_issue")
        self.file_stats: FileStats = FileStats.from_ansible_result(result, "spire_server_file_stats")

    def __get_issues_issues(self) -> str:
        issues_str = "\n".join([value for key, value in self.result.items() if key.endswith("_issue") and value])
        return issues_str or None

    def __get_state(self) -> State:
        return State.from_info(self.spire_server_installed)

    def __get_state_service_status(self) -> SubStateServiceStatus:
        return SubStateServiceStatus.from_info(
            is_healthy=self.spire_server_is_healthy,
            is_service_running=self.spire_server_service_running
        )

    def __get_state_service_installation(self) -> SubStateServiceInstallation:
        return SubStateServiceInstallation.from_info(
            is_service_enabled=self.spire_server_service_enabled,
            is_service_installed=self.spire_server_service_installed
        )

    def to_detected_state(self) -> StateOfServer:
        return StateOfServer(
            state=self.__get_state(),
            substate_service_installation=self.__get_state_service_installation(),
            substate_service_status=self.__get_state_service_status()
        )

    def to_ansible_return_data(self) -> Dict[str, Union[str, bool, Dict[str, Any]]]:
        state_data = self.to_detected_state().to_ansible_return_data()
        return {**state_data,
                "actual_spire_server_version": self.spire_server_version,
                "actual_spire_server_trust_domain_id": self.spire_server_trust_domain_id,
                "actual_spire_server_executable_path": self.spire_server_executable_path,
                "actual_spire_server_get_info_issue": self.__get_issues_issues(),
                "actual_spire_server_get_info_result": self.result
                }


class ServerActionData:
    def __init__(self) -> None:
        self.local_temp_work_dir: str = None
        self.server_templates: ServerTemplates = None
        self.join_token: str = None
        self.spire_server_bundle: str = None
        self.spire_server_info: ServerInfoResultAdapter = ServerInfoResultAdapter({})
        self.downloaded_dist_path: str = None
        self.expected_state: StateOfServer = None
        self.dirs: ServerDirs = None
        self.expected_file_modes: FileModes = None
        self.expected_file_modes_effective: FileModes = None
        self.server_service_return: Dict[str, Any] = None
        self.expected_config: ExpectedConfig = None
        self.expected_stats_by_mode: ExpectedStatsByMode = None
        self.expected_file_stats: FileStats = None
        self.expected_user: User = None

    def to_ansible_return_data(self) -> Dict[str, Any]:
        actual_state_result_data = self.spire_server_info.to_ansible_return_data()
        return {**actual_state_result_data}

    def diff(self) -> DiffSpireCmptActualExpected:
        # TODO move resource(uri) into diff (when executable has moved? how to model that)
        #info = self.spire_server_info
        expected: ExpectedConfig = self.expected_config
        actual: ServerInfoResultAdapter = self.spire_server_info
        dirs: ServerDirs = self.dirs
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
                version_actual=actual.spire_server_version,
                version_expected=expected.spire_version
            )
        ]
        state_diff = StateOfServerDiff(
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
            env_file_digest_diff
        ]
        scope_diff = StrResourceDiff(
            resource_id="spire-server-service-scope",
            actual=Scope.noneOrScope(actual.spire_server_service_scope),
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
        server_templates: ServerTemplates,
        expected_state: State,
        expected_spire_version: str,
        expected_service_scope: Scope,
        task_args: Dict[str, Any] = None,

    ):
        self.env_file: str = None
        self.service_file: str = None
        self.conf_file: str = None
        self.service_file_disgest: str = None
        self.config_file_digest: str = None
        self.spire_version: str = None
        self.service_scope: Scope = None

        if expected_state == State.present:
            self.service_scope = expected_service_scope
            self.spire_version = expected_spire_version
            #server_templates: ServerTemplates = action_data.server_templates
            extra_vars_service_env: Dict[str, str] = {}

            template_resources = [
                SpireTemplateRes(
                    label="service.env", src=server_templates.tmpl_service_env,
                    extra_vars=extra_vars_service_env),
                SpireTemplateRes(
                    label="service", src=server_templates.tmpl_service,
                    extra_vars={**task_args}),
                SpireTemplateRes(
                    label="conf", src=server_templates.tmpl_conf,
                    extra_vars={**task_args})
            ]
            self.env_file, self.service_file, self.conf_file = [
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
            module_fq_name="io_patricecongo.spire.spire_server")
        self.action_data: ServerActionData = ServerActionData()
        self.diff_actual_expected: DiffSpireCmptActualExpected = None

    def _ensure_dir_structure_and_binary_available(
            self, task_vars: Dict[str, Any] = None
    ) -> None:
        file_modes = self.action_data.expected_file_modes_effective
        downloaded_spire_dist_path = self.action_data.downloaded_dist_path
        dirs: ServerDirs = self.action_data.dirs
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
            "/bin/spire-server")

        self._copy_from_controller_to_target(
            copy_task_label=f"spire-server({spire_server_binary_extracted_path})",
            src=spire_server_binary_extracted_path,
            dest=dirs.install_dir_bin,
            sec_attributes={
                "owner": self.get_install_file_owner(),
                "mode": file_modes.mode_file_exe
            },
            task_vars=task_vars,
        )
        return

    def _get_spire_server_service_name(self) -> str:
        return cast(str, self._task.args.get("spire_server_service_name"))

    def _get_service_scope_str(self) -> str:
        return cast(str, self._task.args.get("spire_server_service_scope"))

    def _get_expected_service_scope(self) -> Scope:
         scope_str = self._get_service_scope_str()
         if scope_str:
            return Scope.by_name(scope_str)
         return Scope.scope_system

    def get_expected_version(self) -> str:
        return cast(str, self._task.args.get("spire_server_version"))

    def __ensure_expected_config_available_locally(
            self, task_vars: Dict[str, Any] = None,
    ) -> None:
        action_data = self.action_data

        expected_state = StateOfServer.from_task_args(self._task.args)
        action_data.expected_state = expected_state

        action_data.expected_user = self.remote_user_data()

        file_modes = FileModes.from_dict(
            data=self._task.args,
            mapping= {
                "mode_dir": "spire_server_install_dir_mode",
                "mode_file_not_exe": "spire_server_install_file_mode",
                "mode_file_exe": "spire_server_install_file_mode_exe"
            }
        )
        action_data.expected_file_modes = file_modes

        state = expected_state.state
        action_data.expected_config = ExpectedConfig(
            exe_template_on_localhost=self._exe_template_on_localhost,
            server_templates=action_data.server_templates,
            expected_state=state,
            expected_spire_version=self.get_expected_version(),
            expected_service_scope=self._get_expected_service_scope(),
            task_args=self._task.args
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
        owner: str = self._get_str_from_original_task_args("spire_server_install_file_owner")
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
        dirs: ServerDirs = action_data.dirs

        #(label,source,destination)
        copy_task_specs =[
            ("server.env", config.env_file, dirs.path_env_file),
            ("server.conf", config.conf_file, dirs.path_conf_file),
            ("spire_server.service", config.service_file, dirs.path_service_file)
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

    def _wait_for_spire_server_healthy(self, task_vars: Dict[str, Any] = None) -> None:
        def found_that_server_is_healthy() -> bool:
            info = self.action_data.spire_server_info
            is_healthy = info.spire_server_is_healthy
            return is_healthy

        import time
        self._get_spire_server_info(task_vars=task_vars)
        timeout = self._get_float_from_original_task_args("spire_server_healthiness_probe_timeout_seconds")
        if timeout is None:
            return
        start = time.time()
        while not found_that_server_is_healthy() and (time.time() - start) < timeout:
            time.sleep(1)
            self._get_spire_server_info(task_vars=task_vars)

    def _get_spire_server_info(
            self, task_vars: Dict[str, Any] = None
    ) -> None:
        original_task_args = self._task.args
        service_scope = self._get_service_scope_str()
        dirs: ServerDirs = self.action_data.dirs
        module_args = {
            "spire_server_config_dir": dirs.config_dir,
            "spire_server_data_dir": dirs.data_dir,
            "spire_server_install_dir": dirs.install_dir,
            "spire_server_service_dir": dirs.service_dir,
            "spire_server_log_dir": dirs.log_dir,
            "spire_server_registration_uds_path":
                self._get_str_from_original_task_args("spire_server_registration_uds_path"),
            "spire_server_service_name": dirs.service_name,
            "spire_server_service_scope": service_scope
        }

        cmd_task_vars = task_vars.copy()
        # 'io_patricecongo.spire.plugins.modules.spire_server_info',#
        with self.check_mode_and_diff_being_no():
            module_ret = self._execute_module(
                module_name='io_patricecongo.spire.spire_server_info',
                module_args=module_args,
                task_vars=cmd_task_vars, tmp=None)
        #module_ret: Dict[str,Any] = {}
        self._display.vvv(f"spire_server_info module_ret={module_ret}")
        assert_task_did_not_failed(module_ret, "failed to run spire_server_info")
        server_info = ServerInfoResultAdapter(module_ret)

        self.action_data.spire_server_info = server_info
        return

    def stop_spire_server(self, task_vars: Dict[str, Any]) -> None:
        # TODO this will work only if the dir structure did not change
        # if th current installation does not have the same dirs structure
        #   the spire_serve module will fail
        #   complaining that the server and its service component are not installed

        # TODO scope changes is also an issue
        #   reason: executor and scope mismatch
        #   e.g.    - root calling <systemctl --user ..>
        #           - user (through su) calling <systemctl --system ...>

        def service_state_to_stopped(task_args: Dict[str, Any]) -> Dict[str, Any]:
            spire_server_info = self.action_data.spire_server_info
            current_version = spire_server_info.spire_server_version

            return {
                **task_args,
                "substate_service_status": SubStateServiceStatus.stopped.name,
                "spire_server_version": current_version
            }
        outcome = self._execute_actual_spire_ansible_module(
            task_vars=task_vars,
            task_args_mapper=service_state_to_stopped
        )
        sos = StateOfServer.from_ansible_return_data(task_outcome=outcome)
        if sos.substate_service_status != SubStateServiceStatus.stopped:
            msg = f"""Fail to stop pire-server:
                    state-of-server:{sos}
                    task-outcome: {outcome}
                    """
            raise RuntimeError(msg)

    def need_spire_binary_change(self) -> bool:
        need_change: bool = self.diff_actual_expected.need_binary_change(
            bin_file=self.action_data.dirs.path_executable
        )
        return need_change

    def cleanup(self, force: bool = False) -> None:
        if force or not self._task.async_val:
            ltemp = self.action_data.local_temp_work_dir
            if ltemp:
                shutil.rmtree(ltemp)

        super().cleanup(force=force)

    def run(
        self, tmp: Any = None, task_vars: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        super(ActionModule, self).run(tmp, task_vars)

        tv = dict(task_vars)
        changed = False
        failed_contrib: Dict[str, Any] = {}
        try:
            self.action_data.server_templates = ServerTemplates()
            # TODO what about cleanup? this temp dir creation does not use ansible mechanism.
            # so it will not be cleanup automatically
            # - use ansible creation mechanims
            # - or register temp dir for deletion
            self.action_data.local_temp_work_dir = make_local_temp_work_dir("spire-server-work-dir")
            self.action_data.dirs = ServerDirs.from_ansible_src(
                                                self._get_str_from_original_task_args)
            self.__ensure_expected_config_available_locally(task_vars=tv)
            self._get_spire_server_info(task_vars=tv)
            self.diff_actual_expected = self.action_data.diff()
            self._display.vvvv(f"---------check_mode={self.get_check_mode()}, diff={self.get_diff_mode()}")
            if self.get_check_mode():
                return {
                    'changed': self.diff_actual_expected.need_change(),
                    **self.diff_actual_expected.ansible_diff_outcome_part(
                        diff_activated=self.get_diff_mode()
                    )
                }

            if self.diff_actual_expected.need_change():
                changed = True
                if State.present == self.action_data.expected_state.state:
                    # stop_spire_server_if_started()
                    if self.action_data.spire_server_info.spire_server_service_running:
                        self.stop_spire_server(task_vars=tv)
                    # backup_old_spire_server() backup on target_node, need to specify backup dir
                    self.action_data.downloaded_dist_path = self._download_spire_release(
                        download_decider=self.need_spire_binary_change
                    )
                    self._ensure_dir_structure_and_binary_available(task_vars=tv)
                    self._ensure_service_files_installed(task_vars=tv)
                self._execute_actual_spire_ansible_module(task_vars=tv)
                self._get_spire_server_info(task_vars=tv)
                diff_after_change: DiffSpireCmptActualExpected = self.action_data.diff()
                failed_contrib = diff_after_change.ansible_failed_outcome_part_given_no_diff_expected()
        except Exception as e:
            msg = f"""Error while running spire-server action:
                    message:{str(e)}
                    stacktrace: {logging.get_exception_stacktrace(e)}
                    action_data : {self.action_data}
                    """
            self._display.v(msg)
            raise e
        else:
            ret: Dict[str, Any] = {
                'changed': changed,
                **failed_contrib,
                **self.diff_actual_expected.ansible_diff_outcome_part(
                        diff_activated=self.get_diff_mode()
                ),
                **self.action_data.to_ansible_return_data(),
            }
            return ret
