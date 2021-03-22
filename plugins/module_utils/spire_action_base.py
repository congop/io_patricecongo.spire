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
from abc import abstractmethod
from datetime import datetime, time, timezone
import os
from os.path import dirname
from typing import Any, Callable, Dict, Generator, List, NamedTuple, Tuple, Union, cast

from contextlib import contextmanager

from ansible import constants
from ansible.playbook import task as module_task
from ansible.plugins.action import ActionBase

from ansible_collections.io_patricecongo.spire.plugins.module_utils import strings
from ansible_collections.io_patricecongo.spire.plugins.module_utils.file_stat import RemoteFileAccessFacade
from ansible_collections.io_patricecongo.spire.plugins.module_utils.users import User

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
from ansible_collections.io_patricecongo.spire.plugins.module_utils.net_utils import (
    is_localhost,
    url_filename,
)

from ansible_collections.io_patricecongo.spire.plugins.module_utils.module_outcome import (
    assert_shell_or_cmd_task_successful,
    assert_task_did_not_failed
)

def _identity(m: Dict[str,Any]) -> Dict[str,Any]:
    return m

def make_local_temp_work_dir(temp_dir_prefix:str) -> str:
    local_tempdir: str = tempfile.mkdtemp(
                            dir=constants.DEFAULT_LOCAL_TMP,
                            prefix=temp_dir_prefix)
    return local_tempdir


class SpireTemplateRes(NamedTuple):
    label: str
    src: str
    extra_vars: Dict[str, Any]


# https://gist.github.com/ju2wheels/408e2d34c788e417832c756320d05fb5
# use_vars = task_vars.get('ansible_delegated_vars')[self._task.delegate_to]
# /home/patdev/software/ansible/ansible-modules-spire/.venv/lib/python3.6/site-packages/ansible/plugins/action/__init__.py
#  @ 155  def _configure_module
class SpireActionBase(ActionBase,RemoteFileAccessFacade):  # type: ignore[misc]
    """'abstract' class which hold base feature used to build spire_ser and spire-agent action.
    """
    def __init__(
        self, task: Task, connection: ConnectionBase,
        play_context: PlayContext, loader: dataloader.DataLoader,
        templar: Templar, shared_loader_obj: plugins_loader,
        module_fq_name:str
    ) -> None:
        """init for the spire action base.
        Params:
            module_fq_name
                is the full qualified module nane
                io_patricecongo.spire.spire_agent --> for the spire agent
                io_patricecongo.spire.spire_server --> for the spire server
            ...
        """
        super().__init__(
            task=task, connection=connection, play_context=play_context,
            loader=loader, templar=templar,
            shared_loader_obj=shared_loader_obj)
        self.module_fq_name:str = module_fq_name

    def _get_current_spire_target_host(self, task_vars: Dict[str, Any]) -> str:
        return cast(str, task_vars['inventory_hostname'])

    def _copy_from_controller_to_target(
            self, task_vars: Dict[str, Any],
            copy_task_label: str,
            src: str, dest: str,
            sec_attributes: Dict[str, Any]
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

        self._display.vvv(f"""executing copy {copy_task_label} to target node:
            copy_module_args: {copy_module_args},
            src.exists: {os.path.exists(src)}
            """)
        original_task: Task = self._task
        current_target_host = self._get_current_spire_target_host(task_vars=task_vars)
        copy_task_name = f"{original_task.get_name()}-copy-spire-component"
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


    def _exe_template_on_localhost(self, res: SpireTemplateRes) -> str:
        template_label = res.label
        template_src = res.src
        extra_vars = res.extra_vars
        target_host_local = "localhost"
        template_dest_local = self.__make_tempfile_name(prefix="spire_server", suffix=template_label)
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
            sub_task_ret: Dict[str, Any] = normal_action.run(task_vars=task_vars)
        finally:
            # self._task = original_task
            pass
        return sub_task_ret

    def _get_str_from_original_task_args(self, key: str) -> str:
        val: str = self._task.args.get(key)
        if val is None:
            return None
        if isinstance(val, str):
            return str(val)
        raise ValueError(f"str expected for key={key}; but got {type(val)}; value={val}")
        #return cast(str, self._task.args.get(key))

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

    @abstractmethod
    def get_expected_version(self) -> str:
        pass
        #raise NotImplementedError("Template method please implement it in the concrete class")

    @contextmanager
    def check_mode_and_diff_being_no(self) -> Generator[None,None,None]:
        # final check_mode and diff value set using play_context
        # @ ActionBase def _update_module_args(self, module_name, module_args, task_vars):
        #   module_args['_ansible_check_mode'] set according to self._play_context.check_mode
        #   module_args['_ansible_diff'] = self._play_context.diff
        check_mode = self.get_check_mode()
        pctx_check_mode = self._play_context.check_mode
        pctx_diff = self._play_context.diff
        diff = self.get_diff_mode()
        try:
            self._play_context.check_mode = False
            self._play_context.diff = False
            self.set_check_mode(False)
            self.set_diff_mode(False)
            yield
        finally:
            self.set_check_mode(check_mode)
            self.set_diff_mode(diff)
            self._play_context.check_mode = pctx_check_mode
            self._play_context.diff = pctx_diff

    def _download_spire_release(self, download_decider: Callable[[],bool]) -> str:
        if not download_decider():
            from . import randoms
            hint_as_file_name = randoms.random_file_name_with_datetime("spire_download_not_need")
            return os.path.join("/tmp", hint_as_file_name)
        # Using the controller as download platform.
        # Idea: You may have a dedicated download node for security and performance reason

        target_host = "localhost"

        download_target_dir = os.path.join(constants.DEFAULT_LOCAL_TMP, "spire")
        os.makedirs(name=download_target_dir, exist_ok=True)
        url = self._get_str_from_original_task_args("spire_download_url")
        filename = url_filename(url)
        if not filename:
            version = self.get_expected_version()
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

        get_url_ret = self._run_sub_task(task_data=data, hostname=target_host)
        assert_task_did_not_failed(
            get_url_ret,
            f"Fail to download spire binary with  get_url({delegate_to_old} --> {target_host})")

        return cast(str,get_url_ret.get("dest"))

    def _execute_actual_spire_ansible_module(
        self,
        task_vars: Dict[str, Any],
        task_args_mapper: Callable[[Dict[str,Any]], Dict[str,Any]] = _identity
    ) -> Dict[str, Any]:
        task_args = task_args_mapper(self._task.args)
        ret = self._execute_module(
            module_name=self.module_fq_name,
            module_args=task_args,
            task_vars=task_vars)
        if ret.get("failed", False):
            raise RuntimeError(f"spire agent module failed: {ret}")
        return cast(Dict[str, Any], ret)

    def remote_stat(
            self, task_vars: Dict[str, Any],
            file_path: str,
    ) -> Dict[str, Any]:
        #- name: Get stats of a file
        # ansible.builtin.stat:
        #     path: /etc/foo.conf
        module_args = {
            "path": file_path
        }
        cmd_task_vars = {**task_vars}
        with self.check_mode_and_diff_being_no():
            module_ret = self._execute_module(
                module_name='ansible.builtin.stat',
                module_args=module_args,
                task_vars=cmd_task_vars)
        return cast(Dict[str, Any], module_ret)

    def create_remote_file(
            self,
            task_vars: Dict[str, Any],
            file_path: str,
            state: str,
            mode: str,
            module_args_overrides: Dict[str,Any] = None
    ) -> Dict[str, Any]:
        # TODO what about owner???
        #- name: Create a directory if it does not exist
        # ansible.builtin.file:
        #     path: /etc/some_directory
        #     state: directory
        #     mode: '0755'
        #for expected_dir in expected_dirs:
        if module_args_overrides is None:
            module_args_overrides = {}
        module_args = {
            "path": file_path,
            "state": state,
            "mode": mode,
            "recurse": "no", # "yes" only valid if state==directory
            **module_args_overrides
        }
        cmd_task_vars = {**task_vars}
        with self.check_mode_and_diff_being_no():
            module_ret = self._execute_module(
                module_name='ansible.builtin.file',
                module_args=module_args,
                task_vars=cmd_task_vars, tmp=None)
        return cast(Dict[str, Any], module_ret)


    def create_remote_tmp_dir(self) -> str:
        return cast(str, self._make_tmp_path())

    def remove_remote_tmp_dir(self, path: str) -> None:
        self._remove_tmp_path(path)

    def _create_remote_dirs(
            self, task_vars: Dict[str, Any],
            expected_dirs: List[str],
            mode: str
    ) -> None:
        # TODO what about owner???
        for expected_dir in expected_dirs:
            self.create_remote_file(
                file_path=expected_dir,
                mode=mode,
                state="directory",
                task_vars=task_vars
            )

    def execute_cmd_on_target(self, cmd:str) -> Dict[str, Any]:
        ret: Dict[str, Any] = self._low_level_execute_command(cmd=cmd)
        assert_shell_or_cmd_task_successful(ret, f"fail to remote call {cmd}")
        return ret

    def remote_user_data(self) -> User:
        cmd_passwdentry = "getent passwd $(id -u)"
        ret: Dict[str, Any] = self._low_level_execute_command(cmd=cmd_passwdentry)
        assert_shell_or_cmd_task_successful(ret, f"fail to remote call {cmd_passwdentry}")
        stdout = strings.trim_to_none(ret["stdout"])
        if not stdout:
            raise RuntimeError(f"stdout exected: ret={ret}")
        user = User.from_passwd_entry(stdout)

        return user

    def get_diff_mode(self) -> bool:
        task: Task = self._task
        diff = task.diff
        return bool(diff)

    def get_check_mode(self) -> bool:
        task: Task = self._task
        check_mode = task.check_mode
        return bool(check_mode)

    def set_diff_mode(self, diff: bool) -> None:
        task: Task = self._task
        task.diff = diff

    def set_check_mode(self, check_mode: bool) -> None:
        task: Task = self._task
        task.check_mode = check_mode

    def run(
        self, tmp: Any = None, task_vars: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        ret: Dict[str,Any] = super(SpireActionBase, self).run(tmp, task_vars)
        return ret
