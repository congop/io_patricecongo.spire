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
from typing import Any, Callable, Dict, List, NamedTuple, Tuple, Union, cast

from ansible import constants
from ansible.playbook import task as module_task
from ansible.plugins.action import ActionBase

try:
    from ansible.modules import get_url
except (ModuleNotFoundError, ImportError):
    # for ansible 2.9.x
    # from ansible.modules.net_tools.basics import get_url
    import importlib
    get_url = importlib.import_module("ansible.modules.net_tools.basics.get_url")

import tempfile
from urllib.parse import urlparse

from ansible.inventory.host import Host
from ansible.inventory.manager import InventoryManager
from ansible.parsing import dataloader
from ansible.playbook.play import Play
from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task
from ansible.plugins import loader as plugins_loader
from ansible.plugins.connection.__init__ import ConnectionBase
from ansible.plugins.connection.local import Connection
from ansible.template import Templar
from ansible.vars.manager import VariableManager
from ansible_collections.io_patricecongo.spire.plugins.module_utils import join_token, logging, strings
from ansible_collections.io_patricecongo.spire.plugins.module_utils.agent_templates.resources import (
    AgentTemplates,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_registration_info_cmd import (
    AgentRegistrationEntry,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    State,
    StateOfAgent,
    SubStateAgentRegistered,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)

from ansible_collections.io_patricecongo.spire.plugins.module_utils.net_utils import(
    is_localhost,
    url_filename
)

from ansible_collections.io_patricecongo.spire.plugins.module_utils.module_outcome import(
    assert_task_did_not_failed,
    assert_shell_or_cmd_task_successful
)


def make_local_temp_work_dir() -> str:
    local_tempdir: str = tempfile.mkdtemp(
                            dir=constants.DEFAULT_LOCAL_TMP,
                            prefix="spire-agent-work-dir")
    return local_tempdir


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


class AgentInfoResultAdapter:
    def __init__(self, result: Dict[str, Any]) -> None:
        result = result or {}
        self.result = result or {}
        self.spire_agent_installed: bool = result.get("spire_agent_installed", "False")
        self.spire_agent_spiffe_id: str = result.get("spire_agent_spiffe_id")
        self.spire_agent_serial_number: str = result.get("spire_agent_serial_number")
        self.spire_agent_spiffe_id_issue: str = result.get("spire_agent_spiffe_id_issue")
        self.spire_agent_version: str = result.get("spire_agent_version")
        self.spire_agent_version_issue: str = result.get("spire_agent_version_issue")
        self.spire_agent_executable_path: str = result.get("spire_agent_executable_path")
        self.spire_agent_trust_domain_id: bool = result.get("spire_agent_trust_domain_id")
        self.spire_agent_trust_domain_id_issue: str = result.get("spire_agent_trust_domain_id_issue")
        self.spire_agent_is_healthy: bool = result.get("spire_agent_is_healthy", False)
        self.spire_agent_is_healthy_issue: str = result.get("spire_agent_is_healthy_issue")
        self.spire_agent_service_installed: bool = result.get("spire_agent_service_installed", False)
        self.spire_agent_service_installed_issue: str = result.get("spire_agent_service_installed_issue")
        self.spire_agent_service_running: bool = result.get("spire_agent_service_running", False)
        self.spire_agent_service_running_issue: str = result.get("spire_agent_service_running_issue")
        self.spire_agent_service_enabled: bool = result.get("spire_agent_service_enabled", False)
        self.spire_agent_service_enabled_issue: str = result.get("spire_agent_service_enabled_issue")
        self.is_registered: bool = False

    def spire_agent_serial_number_as_int(self) -> int:
        '''Return the serial number as interger  or -1 if no value is avalaible yet'''
        if self.spire_agent_serial_number:
            return int(self.spire_agent_serial_number)
        return None

    def __get_issues_issues(self) -> str:
        issues_str = "\n".join([value for key, value in self.result.items() if key.endswith("_issue") and value])
        return issues_str or None

    def __get_state_registered(self) -> SubStateAgentRegistered:
        if self.is_registered:
            return SubStateAgentRegistered.yes
        else:
            return SubStateAgentRegistered.no

    def __get_state(self) -> State:
        if self.spire_agent_installed:
            return State.present
        else:
            return State.absent

    def __get_state_service_status(self) -> SubStateServiceStatus:
        if self.spire_agent_is_healthy:
            return SubStateServiceStatus.healthy
        elif self.spire_agent_service_running:
            return SubStateServiceStatus.started
        else:
            return SubStateServiceStatus.stopped

    def __get_state_service_installation(self) -> SubStateServiceInstallation:
        if self.spire_agent_service_enabled:
            return SubStateServiceInstallation.enabled
        elif self.spire_agent_service_installed:
            return SubStateServiceInstallation.installed
        else:
            return SubStateServiceInstallation.not_installed

    def to_detected_state(self) -> StateOfAgent:
        return StateOfAgent(
            state=self.__get_state(),
            substate_agent_registered=self.__get_state_registered(),
            substate_service_installation=self.__get_state_service_installation(),
            substate_service_status=self.__get_state_service_status()
        )

    def to_ansible_return_data(self) -> Dict[str, Union[str, bool, Dict[str, Any]]]:
        state_data = self.to_detected_state().to_ansible_return_data()
        return {**state_data,
                "actual_spire_agent_version": self.spire_agent_version,
                "actual_spire_agent_serial_number": self.spire_agent_serial_number,
                "actual_spire_agent_spiffe_id": self.spire_agent_spiffe_id,
                "actual_spire_agent_trust_domain_id": self.spire_agent_trust_domain_id,
                "actual_spire_agent_executable_path": self.spire_agent_executable_path,
                "actual_spire_agent_get_info_issue": self.__get_issues_issues(),
                "actual_spire_agent_get_info_result": self.result
                }


class AgentDirs:
    def __init__(self, lookup_func: Callable[[str], str]):
        self.spire_agent_config_dir: str = lookup_func("spire_agent_config_dir")
        self.spire_agent_data_dir: str = lookup_func("spire_agent_data_dir")
        self.spire_agent_install_dir: str = lookup_func("spire_agent_install_dir")
        self.spire_agent_install_dir_bin: str = os.path.join(self.spire_agent_install_dir, "bin")
        self.spire_agent_service_dir: str = lookup_func("spire_agent_service_dir")
        self.spire_agent_log_dir: str = lookup_func("spire_agent_log_dir")
        self.spire_agent_service_name = lookup_func("spire_agent_service_params_name")
        self.spire_agent_service_filename = self.spire_agent_service_name
        if self.spire_agent_service_filename.endswith(".service"):
            self.spire_agent_service_name = os.path.splitext(self.spire_agent_service_name)[0]
        else:
            self.spire_agent_service_filename = f"{self.spire_agent_service_name}.service"

    def path_agent_conf(self) -> str:
        return os.path.join(self.spire_agent_config_dir, "agent.conf")

    def path_agent_env(self) -> str:
        return os.path.join(self.spire_agent_config_dir, "agent.env")

    def path_trust_bundle_pem(self) -> str:
        return os.path.join(self.spire_agent_config_dir, "trust_bundle.pem")

    def path_agent_service(self) -> str:
        return os.path.join(self.spire_agent_service_dir, self.spire_agent_service_filename)


class AgentActionData:
    def __init__(self) -> None:
        self.local_temp_work_dir: str = None
        self.agent_templates: AgentTemplates = None
        self.join_token: str = None
        self.spire_server_bundle: str = None
        self.spire_agent_info: AgentInfoResultAdapter = AgentInfoResultAdapter({})
        self.spire_server_version: str = None
        self.downloaded_dist_path: str = None
        self.expected_state: StateOfAgent = None
        self.agent_dirs: AgentDirs = None
        self.agent_service_return: Dict[str, Any] = None

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


# https://gist.github.com/ju2wheels/408e2d34c788e417832c756320d05fb5
# use_vars = task_vars.get('ansible_delegated_vars')[self._task.delegate_to]
# /home/patdev/software/ansible/ansible-modules-spire/.venv/lib/python3.6/site-packages/ansible/plugins/action/__init__.py
#  @ 155  def _configure_module
class ActionModule(ActionBase):  # type: ignore[misc]

    def __init__(
        self, task: Task, connection: ConnectionBase,
        play_context: PlayContext, loader: dataloader.DataLoader,
        templar: Templar, shared_loader_obj: plugins_loader
    ) -> None:
        super().__init__(
            task=task, connection=connection, play_context=play_context,
            loader=loader, templar=templar,
            shared_loader_obj=shared_loader_obj)
        self.action_data: AgentActionData = AgentActionData()

    def _get_spire_server(self) -> str:
        return "spire_server"

    def _ensure_spire_agent_dir_structure_and_binary_available(
            self, task_vars: Dict[str, Any] = None
    ) -> None:
        def extract_spire_agent_binary(downloaded_spire_dist_path: str) -> str:
            import os
            import tarfile
            with tarfile.open(downloaded_spire_dist_path) as tar:
                spire_agent_binary_as_list = [
                    e for e in tar
                    if str(e.name).endswith('/bin/spire-agent') and e.name.startswith("./")]
                if 1 != len(spire_agent_binary_as_list):
                    tar_gz_ls = [e.name for e in tar]
                    msg = f"""could not find spire-agent binaries in tar.gz
                            tar-gz: {downloaded_spire_dist_path}
                            tar-gz-content: {tar_gz_ls}
                        """
                    raise RuntimeError(msg)
                target_dir = os.path.dirname(downloaded_spire_dist_path)
                tar.extractall(members=spire_agent_binary_as_list, path=target_dir)
                target_file = os.path.join(target_dir, spire_agent_binary_as_list[0].name)
                target_file = os.path.normpath(target_file)

            return target_file

        downloaded_spire_dist_path = self.action_data.downloaded_dist_path
        agent_dirs: AgentDirs = self.action_data.agent_dirs
        # TODO use file module instead
        # - name: Ensure spire-agent data dir (e.g. /var/lib/spire-agent) is available
        #     file:
        #         path: "{{ spire_agent_data_dir }}"
        #         state: directory
        # !!! maybe with_items to make multiple directories at one instead of manual iteration
        #   with_items:
        #     - { path: "ca.pem", mode: "{{ etcd_config_dir }}", serole:.... }

        script_create_dir_struct = f"""mkdir -p {agent_dirs.spire_agent_config_dir} &&
            mkdir -p {agent_dirs.spire_agent_data_dir} &&
            mkdir -p {agent_dirs.spire_agent_install_dir_bin} &&
            mkdir -p {agent_dirs.spire_agent_service_dir} &&
            mkdir -p {agent_dirs.spire_agent_log_dir}
            """
        become = self._task.become
        rc, stdout, stderr = self._connection.exec_command(
                                            script_create_dir_struct,
                                            in_data=None, sudoable=become)
        if rc != 0:
            raise RuntimeError(f"""fail to create dir structure:
                rc={rc}
                stdout={stdout}
                stderr={stderr}
                script_create_dir_struct={script_create_dir_struct}
                """)

        spire_agent_binary_extracted_path = extract_spire_agent_binary(downloaded_spire_dist_path)

        copy_module_args = {
            "src": spire_agent_binary_extracted_path,
            "remote_src": "no",
            "dest": agent_dirs.spire_agent_install_dir_bin,
            "owner": self._get_str_from_original_task_args("spire_agent_install_file_owner"),
            "mode": self._get_str_from_original_task_args("spire_agent_install_file_mode_exe")

        }
        self._display.vvv(
            f"""executing copy to spire_agent: {copy_module_args},
                src.exists: {os.path.exists(spire_agent_binary_extracted_path)}
            """)
        original_task: Task = self._task
        # copy_task_data = {
        #     "name": f"{original_task.get_name()}-copy-spire-agent",
        #     "copy": copy_module_args
        # }
        current_target_host = task_vars['inventory_hostname']
        copy_task_name = f"{original_task.get_name()}-copy-spire-agent"
        copy_play_name = f"Ansible Sub Play - {copy_task_name}"
        play_source = dict(
            name=copy_play_name,
            hosts=[current_target_host],
            gather_facts='no',
            tasks=[
                dict(name=copy_task_name, action=dict(module='copy', args=copy_module_args)),
            ]
        )

        # Instantiating a play because copy need Task.get_path()
        #   which will failed if Task._ds is not set and Task._parent._play is not set
        play: Play = Play.load(data=play_source,
                               variable_manager=original_task.get_variable_manager(),
                               loader=original_task.get_loader(),
                               vars=self._play_context.vars.copy())
        play_tasks = play.get_tasks()
        play_tasks_copy = play_tasks[0][0]

        copy_action = self._shared_loader_obj.action_loader.get('copy',
                                                                task=play_tasks_copy,
                                                                connection=self._connection,
                                                                play_context=self._play_context,
                                                                loader=self._loader,
                                                                templar=self._templar,
                                                                shared_loader_obj=self._shared_loader_obj)
        mk_cp_struct_ret = copy_action.run(task_vars=task_vars)

        # self._connection.exec_command(self, cmd, in_data=None, sudoable=True)
        if not (mk_cp_struct_ret and "file" == mk_cp_struct_ret.get("state")):
            msg = f"""Fail to copy spire_agent binary to target host:
                mk_cp_struct_ret={mk_cp_struct_ret}
            """
            raise RuntimeError(msg)
        return

    def _get_current_spire_agent_host(self, task_vars: Dict[str, Any]) -> str:
        return cast(str, task_vars['inventory_hostname'])

    def _copy_from_controller_to_spire_agent(
            self, task_vars: Dict[str, Any],
            copy_task_label: str,
            src: str, dest: str, sec_attributes: Dict[str, Any]
    ) -> None:
        actual_sec_attributes = {}
        if sec_attributes:
            supported_sec_attribute_keys = ["owner", "mode"]
            actual_sec_attributes = {key: value for key, value in sec_attributes.items() if
                                     value and key in supported_sec_attribute_keys}

        copy_module_args = {
            "src": src,
            "remote_src": "no",
            "dest": dest,
            **actual_sec_attributes
        }

        self._display.vvv(f"""executing copy {copy_task_label} to spire_agent:
            copy_module_args: {copy_module_args},
            src.exists: {os.path.exists(src)}
            """)
        original_task: Task = self._task
        current_target_host = self._get_current_spire_agent_host(task_vars=task_vars)
        copy_task_name = f"{original_task.get_name()}-copy-spire-agent"
        copy_play_name = f"Ansible Sub Play - {copy_task_name}"
        play_source = dict(
            name=copy_play_name,
            hosts=[current_target_host],
            gather_facts='no',
            tasks=[
                dict(name=copy_task_name, action=dict(module='copy', args=copy_module_args)),
            ]
        )

        # Instantiating a play because copy need Task.get_path()
        #   which will failed if Task._ds is not set and Task._parent._play is not set
        play: Play = Play.load(data=play_source,
                               variable_manager=original_task.get_variable_manager(),
                               loader=original_task.get_loader(),
                               vars=self._play_context.vars.copy())
        play_tasks = play.get_tasks()
        play_tasks_copy = play_tasks[0][0]

        copy_action = self._shared_loader_obj.action_loader.get('copy',
                                                                task=play_tasks_copy,
                                                                connection=self._connection,
                                                                play_context=self._play_context,
                                                                loader=self._loader,
                                                                templar=self._templar,
                                                                shared_loader_obj=self._shared_loader_obj)
        mk_cp_struct_ret = copy_action.run(task_vars=task_vars)

        # self._connection.exec_command(self, cmd, in_data=None, sudoable=True)
        if not (mk_cp_struct_ret and "file" == mk_cp_struct_ret.get("state")):
            msg = f"""Fail to copy {copy_task_label} to target host {current_target_host}:
                mk_cp_struct_ret={mk_cp_struct_ret}
            """
            raise RuntimeError(msg)
        return

    def __make_tempfile_with_data(self, prefix: str = None, suffix: str = None, data: str = '') -> str:
        fd, template_dest_local = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        with open(fd, mode="wt") as dest_file:
            dest_file.write(data)
        return str(template_dest_local)

    def __make_tempfile_name(self, prefix: str = None, suffix: str = None) -> str:
        local_temp_work_dir: str = self.action_data.local_temp_work_dir
        template_dest_local = tempfile.mktemp(dir=local_temp_work_dir, prefix=prefix, suffix=suffix)
        return template_dest_local

    def _get_spire_agent_service_name(self) -> str:
        return cast(str, self._task.args.get("spire_agent_service_params_name"))

    def _get_spire_agent_service_scope(self) -> str:
        return cast(str, self._task.args.get("spire_agent_service_params_scope"))

    def _ensure_spire_agent_service_files_installed(
            self, task_vars: Dict[str, Any] = None,
    ) -> None:
        class SpireAgentTemplateRes(NamedTuple):
            label: str
            src: str
            extra_vars: Dict[str, Any]

        def exe_template(res: SpireAgentTemplateRes) -> str:
            template_label = res.label
            template_src = res.src
            extra_vars = res.extra_vars
            target_host_local = "localhost"
            template_dest_local = self.__make_tempfile_name(prefix="spire_agent", suffix=template_label)
            original_task: Task = self._task
            task_data = {
                "name": f"{original_task.get_name()}-template-{template_label}",
                "template": {
                    "src": template_src,
                    "dest": template_dest_local
                },
                "vars": extra_vars
            }
            ret = self._run_sub_task(task_data=task_data, hostname=target_host_local, action_name='template')
            if ret.get("failed", False):
                msg = f"""Fail to local template {template_label}:
                    return={ret}
                """
                raise RuntimeError(msg)
            return template_dest_local

        action_data = self.action_data
        agent_templates: AgentTemplates = action_data.agent_templates
        extra_vars_service_env = {"spire_agent_join_token": action_data.join_token}

        template_resources = [
            SpireAgentTemplateRes(label="service.env", src=agent_templates.tmpl_service_env,
                                  extra_vars=extra_vars_service_env),
            SpireAgentTemplateRes(label="service", src=agent_templates.tmpl_service, extra_vars={**self._task.args}),
            SpireAgentTemplateRes(label="conf", src=agent_templates.tmpl_conf, extra_vars={**self._task.args})
        ]
        env_file, service_file, conf_file = [exe_template(tres) for tres in template_resources]
        # TODO sec attribute for each file at least executable vs config vs secrets
        sec_attributes = {
            "owner": self._get_str_from_original_task_args("spire_agent_install_file_owner"),
            "mode": self._get_str_from_original_task_args("spire_agent_install_file_mode")
        }

        agent_dirs: AgentDirs = self.action_data.agent_dirs
        self._copy_from_controller_to_spire_agent(
            task_vars=task_vars, copy_task_label="agent.env", src=env_file,
            dest=agent_dirs.path_agent_env(),
            sec_attributes=sec_attributes.copy())
        self._copy_from_controller_to_spire_agent(
            task_vars=task_vars, copy_task_label="agent.conf", src=conf_file,
            dest=agent_dirs.path_agent_conf(),
            sec_attributes=sec_attributes.copy())

        self._copy_from_controller_to_spire_agent(
            task_vars=task_vars, copy_task_label="spire_agent.service", src=service_file,
            dest=agent_dirs.path_agent_service(),
            sec_attributes=sec_attributes.copy())
        local_trust_bundle = self.__make_tempfile_with_data(
            prefix="trust_bundle", suffix=".pem",
            data=action_data.spire_server_bundle)

        self._copy_from_controller_to_spire_agent(
            task_vars=task_vars, copy_task_label="trust_bundle.pem", src=local_trust_bundle,
            dest=agent_dirs.path_trust_bundle_pem(),
            sec_attributes=sec_attributes.copy())

    def _wait_for_spire_agent_healthy(self, task_vars: Dict[str, Any] = None) -> None:
        def found_that_agent_is_healthy() -> bool:
            info = self.action_data.spire_agent_info
            is_healthy = info.spire_agent_is_healthy
            return is_healthy

        import time
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

        version_ret = self._run_sub_task(task_data=data, hostname=spire_server_host)

        return version_ret

    def _run_sub_task(
            self,
            task_data: Dict[str, Any] = None,
            hostname: str = None,
            action_name: str = 'normal'
    ) -> Dict[str, Any]:
        task_vars, task, host = self._make_module_task_vars(task_data=task_data, hostname=hostname)

        try:
            ansible_host = host.address  # get_name()#task_vars['ansible_host']#:'localhost'
            connection_name = task_vars.get('ansible_connection')  # :'local'
            if not connection_name and is_localhost(host):
                self._display.warning(f"supposing ansible_collection=local for {host}")
                connection_name = "local"
            # TODO What about become and username
            play: Play = Play.load({
                "hosts": hostname},
                variable_manager=task.get_variable_manager(),
                loader=task.get_loader())

            play_context = PlayContext(play=play)
            if not play_context.remote_addr:
                play_context.remote_addr = ansible_host  # cmd_task_vars['ansible_delegated_vars'][spire_server_host][]
                # ...'ansible_host': 'localhost'
                # ...'inventory_hostname':'spire_server'
                # ...'inventory_hostname_short':'spire_server'

            connection: ConnectionBase = self._shared_loader_obj.connection_loader.get(connection_name, play_context,
                                                                                       os.devnull)
            normal_action = self._shared_loader_obj.action_loader.get(action_name,
                                                                      task=task,
                                                                      connection=connection,
                                                                      play_context=play_context,
                                                                      loader=task.get_loader(),
                                                                      templar=self._templar,
                                                                      shared_loader_obj=self._shared_loader_obj)
            version_ret: Dict[str, Any] = normal_action.run(task_vars=task_vars)
        finally:
            # self._task = original_task
            pass
        return version_ret

    def _get_spire_server_version(self, task_vars: Dict[str, Any] = None) -> None:
        version_ret = self._run_spire_server_cmd_sub_task(
            task_vars=task_vars,
            task_cmd_label="version",
            spire_server_cmd_args=["--version"],
            add_uds_path_arg=False)
        spire_server_host = self._get_str_from_original_task_args("spire_server_host")
        assert_shell_or_cmd_task_successful(version_ret,
                                                          f"Fail to get spire-server version on [{spire_server_host}]")
        stdout = version_ret.get("stdout")
        stderr = version_ret.get("stderr")
        self.action_data.spire_server_version = stderr or stdout

    def _get_spire_server_bundle(self, task_vars: Dict[str, Any] = None) -> str:
        # /opt/spire/bin/spire-server bundle show > nestedB/agent/bootstrap.crt
        version_ret = self._run_spire_server_cmd_sub_task(
            task_vars=task_vars,
            task_cmd_label="bundle show",
            spire_server_cmd_args=["bundle", "show"])

        assert_shell_or_cmd_task_successful(version_ret, "Fail to get spire-server bundle show")
        stdout = cast(str, version_ret.get("stdout"))
        self.action_data.spire_server_bundle = stdout
        return stdout

    def _get_join_token(self, task_vars: Dict[str, Any] = None) -> str:

        def args_contrib_ttl() -> List[str]:
            ttl = self._get_str_from_original_task_args("spire_agent_join_token_ttl")
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
        return jointoken  # cast(str,jointoken)

    def _get_str_from_original_task_args(self, key: str) -> str:
        return cast(str, self._task.args.get(key))

    def _get_float_from_original_task_args(self, key: str) -> float:
        value = self._task.args.get(key)
        if value is None:
            return None
        if isinstance(value, float):
            return value
        try:
            return float(value)
        except TypeError as te:
            msg = (f"failed to convert value to float: key={key}, "
                   f"value={value}, value-type:{type(value)} error={str(te)}")
            raise RuntimeError(msg)

    def _get_original_task_args_key(self) -> List[str]:
        return [*self._task.args]

    def _get_spire_agent_info(
            self, task_vars: Dict[str, Any] = None,
            with_registration_check: bool = True
    ) -> None:
        original_task_args = self._task.args
        service_scope = self._get_spire_agent_service_scope()
        agent_dirs: AgentDirs = self.action_data.agent_dirs
        module_args = {
            "spire_agent_config_dir": agent_dirs.spire_agent_config_dir,
            "spire_agent_data_dir": agent_dirs.spire_agent_data_dir,
            "spire_agent_install_dir": agent_dirs.spire_agent_install_dir,
            "spire_agent_socket_path":
                self._get_str_from_original_task_args("spire_agent_socket_path"),
            "spire_agent_service_name": agent_dirs.spire_agent_service_name,
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
                    spiffe_id=agent_info.spire_agent_spiffe_id,
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
        if not agent_info.spire_agent_spiffe_id:
            return AgentRegistrationInfoResultAdapter({})

        spire_server_install_dir = self._get_str_from_original_task_args("spire_server_install_dir")
        uds_path = self._get_str_from_original_task_args("spire_server_registration_uds_path")
        agent_dirs: AgentDirs = self.action_data.agent_dirs
        module_args = {
            "spire_agent_spiffe_id": agent_info.spire_agent_spiffe_id,
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

    def _make_module_task_vars(
            self, task_data: Dict[str, Any], hostname: str = None
    ) -> Tuple[Dict[str, Any], Task, Host]:
        original_task: module_task.Task = self._task
        variable_manager: VariableManager = original_task.get_variable_manager()
        data_loader = original_task.get_loader()
        inventory: InventoryManager = variable_manager._inventory
        host = None if not hostname else inventory.get_host(hostname)
        play_data = {
            "hosts": hostname,
            "tasks": [task_data]
        }
        play: Play = Play.load(play_data,
                               variable_manager=variable_manager,
                               loader=data_loader, vars=None)

        # task: Task = module_task.Task.load(data=task_data,
        #     variable_manager=variable_manager,
        #     loader=data_loader)
        task = play.get_tasks()[0][0]
        task_vars = variable_manager.get_vars(play=play, task=task, host=host)
        return task_vars, task, host

    def _make_task_vars(
            self, task: Task, hostname: str = None, play: Play = None
    ) -> Tuple[Dict[str, Any], Task, Host]:
        variable_manager: VariableManager = task.get_variable_manager()
        # data_loader = task.get_loader()
        inventory: InventoryManager = variable_manager._inventory
        host = None if not hostname else inventory.get_host(hostname)
        task_vars = variable_manager.get_vars(play=play, task=task, host=host)
        return task_vars, task, host

    def _download_spire_release(self) -> None:
        # Using the controller as download platform.
        # Idea: You may have a dedicated download node for security and performance reason

        target_host = "localhost"

        download_target_dir = os.path.join(constants.DEFAULT_LOCAL_TMP, "spire")
        os.makedirs(name=download_target_dir, exist_ok=True)
        version = self._get_str_from_original_task_args("spire_agent_version")
        url = self._get_str_from_original_task_args("spire_download_url")
        filename = url_filename(url)
        if not filename:
            # todo put current host name into name!?!
            filename = f"spire-{version}-linux-x86_64-glibc.tar.gz"
        filepath = os.path.join(download_target_dir, filename)
        delegate_to_old = self._task.delegate_to

        module_args = {
            "url": url,
            "dest": filepath,
        }
        data = {
            "name": f"{self._task.get_name()}-get-url",
            "get_url": module_args,
        }

        version_ret = self._run_sub_task(task_data=data, hostname=target_host)
        assert_task_did_not_failed(
            version_ret,
            f"Fail to download spire binary with  get_url({delegate_to_old} --> {target_host})")

        self.action_data.downloaded_dist_path = version_ret.get("dest")

    def execute_module_spire_agent(self, task_vars: Dict[str, Any]) -> None:
        ret = self._execute_module(
            module_name='io_patricecongo.spire.spire_agent',
            module_args=self._task.args,
            task_vars=task_vars)
        if ret.get("failed", False):
            raise RuntimeError(f"spire agent module failed: {ret}")

    def run(
        self, tmp: Any = None, task_vars: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        super(ActionModule, self).run(tmp, task_vars)

        tv = dict(task_vars)
        changed = False
        try:
            self.action_data.agent_templates = AgentTemplates()
            self.action_data.expected_state = StateOfAgent.from_task_args(self._task.args)
            self.action_data.local_temp_work_dir = make_local_temp_work_dir()
            self.action_data.agent_dirs = AgentDirs(self._get_str_from_original_task_args)

            self._get_spire_agent_info(task_vars=tv)

            if self.action_data.need_change():
                changed = True
                if State.present == self.action_data.expected_state.state:
                    self._get_join_token(task_vars=tv)
                    self._get_spire_server_bundle()
                    self._get_spire_server_version(task_vars=tv)
                    self._download_spire_release()
                    self._ensure_spire_agent_dir_structure_and_binary_available(task_vars=tv)
                    self._ensure_spire_agent_service_files_installed(task_vars=tv)
                self.execute_module_spire_agent(task_vars=tv)
                self._get_spire_agent_info(task_vars=tv)

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
                **self.action_data.to_ansible_return_data()
            }
            return ret
