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
import functools
import json
import os
import re
import sys
from typing import Any, Dict, Generator, NamedTuple, Tuple

# import _pytest.monkeypatch as mp
from ansible.inventory.manager import InventoryManager
from ansible.parsing import dataloader
from ansible.playbook.play import Play
from ansible.playbook.play_context import PlayContext
from ansible.playbook.task import Task
from ansible.plugins import loader as plugins_loader
from ansible.plugins.connection.local import Connection
from ansible.plugins.loader import connection_loader
from ansible.template import Templar
from ansible.vars.manager import VariableManager

# must be imported after the patching of _AnsibleCollectionFinder.find_module
# because the import of an action triggers some setup/loading of ansible-collection stuff
from ansible_collections.io_patricecongo.spire.plugins.action import spire_agent
from ansible_collections.io_patricecongo.spire.plugins.module_utils import systemd
from ansible_collections.io_patricecongo.spire.plugins.module_utils.file_stat import FileModes
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    State,
    StateOfAgent,
    SubStateAgentRegistered,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)
import pytest

from .spire_test_runner import AgentRunner, ServerRunner, subprocess_run_command
from . import test_data

# cmd:chmod u+x /home/spire/.ansible/tmp/ansible-tmp-1599045417.1758895-17492-105838489853076/
#       /home/spire/.ansible/tmp/ansible-tmp-1599045417.1758895-17492-105838489853076/AnsiballZ_get_url.py
# cmd:/usr/bin/python
#       /home/spire/.ansible/tmp/ansible-tmp-1599045417.1758895-17492-105838489853076/AnsiballZ_get_url.py
# regex_get_url_= re.compile("/usr/bin/python\s+.*/AnsiballZ_get_url.py$")
_regex_get_url_ = re.compile(r"/usr/bin/python\s+(.*/AnsiballZ_get_url.py)$")
_regex_command_ = re.compile(r"/usr/bin/python\s+(.*/AnsiballZ_command.py)$")


class SpireRunners(NamedTuple):
    server: ServerRunner
    agent: AgentRunner

    def to_agent_initial_state(
        self, state: StateOfAgent, spire_version: str, file_modes: FileModes
    ) -> None:
        def reject_unsupported_service_installation_stated() -> None:
            supported_states = [SubStateServiceInstallation.enabled]
            if state.substate_service_installation not in supported_states:
                msg = f"""unsupported state:
                            actual: {state.substate_service_installation}
                            supported: {supported_states}
                        """
                raise RuntimeError(msg)

        if state.state == State.absent:
            return
        self.agent.spire_agent_join_token = self.server.generate_join_token(
            additional_spiffe_id=self.agent.additional_spiffe_id,
            ttl=self.agent.join_token_ttl
        )
        self.agent.server_bundle = self.server.get_server_bundle()
        self.agent.install(spire_version)
        self.agent.fix_files_modes(file_modes)
        reject_unsupported_service_installation_stated()
        srv_status = state.substate_service_status
        if SubStateServiceStatus.stopped == srv_status:
            return
        # started or healthy
        self.agent.start(must_be_ready=(SubStateServiceStatus.healthy == srv_status))


@pytest.fixture
def spire_runners() -> Generator[SpireRunners, None, None]:
    server = ServerRunner(
        service_name="spire_server_unit_test",
        scope=systemd.Scope.scope_user,
        run_command=subprocess_run_command
    )
    agent = AgentRunner(
        server_address=server.bind_address,
        server_port=server.bind_port,
        socket_path="/tmp/agent.sock",
        service_name="spire_agent_unit_test",
        scope=systemd.Scope.scope_user,
        run_command=subprocess_run_command,
    )
    runners = SpireRunners(server, agent)
    try:
        yield runners
    finally:
        server_e: Exception = None
        agent_e: Exception = None

        try:
            agent.teardown()
        except Exception as e:
            agent_e = e

        try:
            server.teardown()
        except Exception as e:
            server_e = e

        if agent_e or server_e:
            pytest.fail(f"""teardown was not fully succesfull:
                            server-->{server_e}
                            agent-->{agent_e}
                        """)


def _low_level_execute_command(
    orininal_func,
    cmd: str, sudoable: bool = True, in_data: Any = None,
    executable: str = None, encoding_errors: str = 'surrogate_then_replace',
    chdir: str = None
) -> Dict[str, Any]:
    print(f"""_low_level_execute_command
            cmd-type:{type(cmd)}
            in_data= {in_data}
            cmd:{cmd}
            executable:{executable}
            """)
    if cmd and cmd.endswith(".py"):
        match = _regex_get_url_.search(cmd)
        vers = test_data.spire_version
        if match:
            return {
                "dest": "/tmp/xyz556876/blabla.tar.bz",
                'status_code': 200,
                'md5sum': 'abf47ac4d8d004face4ae9f68d6895d0',
                'elapsed': 5,
                'url':
                    f'https://github.com/spiffe/spire/releases/download/v{vers}/spire-{vers}-linux-x86_64-glibc.tar.gz',
                'state': 'file', 'gid': 1000, 'mode': '0664',
                'stdout': str({}), 'rc': 0}
        match = _regex_command_.search(cmd)
        if match:
            return {"rc": 0,
                    "stdout": json.dumps({
                                    'rc': 0, 'changed': True,
                                    'stdout': '0.10.22', 'stderr': vers})
                    }
    ret_from_original: Dict[str, Any] = orininal_func(
                        cmd=cmd, sudoable=sudoable, in_data=in_data,
                        executable=executable, encoding_errors=encoding_errors,
                        chdir=chdir)
    return ret_from_original


def give_inventory_and_data_loader() -> Tuple[InventoryManager, dataloader.DataLoader, VariableManager]:
    data_loader = dataloader.DataLoader()
    # create the inventory, and filter it based on the subset specified (if any)
    inventory = InventoryManager(loader=data_loader, sources="localhost")
    # inventory.add_host("spire_server",group="all")
    # inventory.add_host("spire_agent",group="all")
    inventory.add_group("all")
    inventory.add_group("ungrouped")
    inventory.add_host("localhost", group="ungrouped")
    inventory.add_host("spire_server", group="ungrouped")
    inventory.add_host("spire_agent", group="ungrouped")

    # create the variable manager, which will be shared throughout
    # the code, ensuring a consistent view of global variables
    var_manager = VariableManager(loader=data_loader, inventory=inventory, version_info=None)
    var_manager.set_host_variable("spire_server", "ansible_connection", "local")
    var_manager.set_host_variable("spire_agent", "ansible_connection", "local")
    var_manager.set_host_variable("spire_server", "ansible_host", "localhost")
    var_manager.set_host_variable("spire_agent", "ansible_host", "localhost")
    python_path = sys.executable
    var_manager.set_host_variable("spire_server", "ansible_python_interpreter", python_path)
    var_manager.set_host_variable("spire_agent", "ansible_python_interpreter", python_path)
    var_manager.set_host_variable("localhost", "ansible_python_interpreter", python_path)

    # spire_agent_host_vars = variable_manager.get_vars(host=inventory.get_host("localhost"))

    return inventory, data_loader, var_manager


@pytest.mark.parametrize(
    "test_case, initial_state, expected_state, outcome_part, expected_local_probing",
    [
        (
            "can_provision_healthy_agent_from_absent",
            StateOfAgent(
                state=State.absent,
                substate_service_installation=None,
                substate_service_status=None,
                substate_agent_registered=None
            ),
            StateOfAgent(
                state=State.present,
                substate_service_installation=SubStateServiceInstallation.enabled,
                substate_service_status=SubStateServiceStatus.healthy,
                substate_agent_registered=SubStateAgentRegistered.yes
            ),
            {
                "changed": True,
                "failed": None,
                'actual_spire_agent_version': test_data.spire_version
            },
            {
                "healthy": True,
                "enabled": True,
                "running": True
            }
        ),
        (
            "nop_if_already_provisioned_healthy_agent",
            StateOfAgent(
                state=State.present,
                substate_service_installation=SubStateServiceInstallation.enabled,
                substate_service_status=SubStateServiceStatus.healthy,
                substate_agent_registered=SubStateAgentRegistered.yes
            ),
            StateOfAgent(
                state=State.present,
                substate_service_installation=SubStateServiceInstallation.enabled,
                substate_service_status=SubStateServiceStatus.healthy,
                substate_agent_registered=SubStateAgentRegistered.yes
            ),
            {
                "changed": False,
                "failed": None,
                'actual_spire_agent_version': test_data.spire_version
            },
            {
                "healthy": True,
                "enabled": True,
                "running": True
            }
        ),
        (
            "nop_if_ensure_absent_from_initial_absent",
            StateOfAgent(
                state=State.absent,
                substate_service_installation=None,
                substate_service_status=None,
                substate_agent_registered=None
            ),
            StateOfAgent(
                state=State.absent,
                substate_service_installation=SubStateServiceInstallation.not_installed,
                substate_service_status=SubStateServiceStatus.stopped,
                substate_agent_registered=SubStateAgentRegistered.no
            ),
            {
                "changed": False,
                "failed": None,
                'actual_spire_agent_version': None
            },
            {
                "healthy": False,
                "enabled": False,
                "running": False
            }
        ),
        (
            "uninstall_if_ensure_absent_from_healthy",
            StateOfAgent(
                state=State.present,
                substate_service_installation=SubStateServiceInstallation.enabled,
                substate_service_status=SubStateServiceStatus.healthy,
                substate_agent_registered=SubStateAgentRegistered.yes
            ),
            StateOfAgent(
                state=State.absent,
                substate_service_installation=SubStateServiceInstallation.not_installed,
                substate_service_status=SubStateServiceStatus.stopped,
                substate_agent_registered=SubStateAgentRegistered.no
            ),
            {
                "changed": True,
                "failed": None,
                'actual_spire_agent_version': None
            },
            {
                "healthy": False,
                "enabled": False,
                "running": False
            }
        ),
    ]
)
def test_pire_agent(
    spire_runners: SpireRunners,
    test_case: str,
    initial_state: StateOfAgent,
    expected_state: StateOfAgent,
    outcome_part: Dict[str, Any],
    expected_local_probing: Dict[str, Any]
) -> None:
    server_runner: ServerRunner = spire_runners.server
    agent_runner: AgentRunner = spire_runners.agent

    server_runner.install_and_start(
        spire_version=test_data.spire_version, must_be_ready=True)
    file_modes = FileModes(
        mode_dir="u=xrw,g=xrw,o=",
        mode_file_not_exe="u=rw,g=rw,o=",
        mode_file_exe="u=xrw,g=xr,o=xr")
    #spire_runners.to_server_initial_state(initial_state, initial_version, file_modes)
    spire_runners.to_agent_initial_state(initial_state, test_data.spire_version, file_modes)
    inventory, data_loader, var_manager = give_inventory_and_data_loader()

    play: Play = Play.load({"hosts": "spire_agent"},
                           variable_manager=var_manager,
                           loader=data_loader
                           )

    play_context = PlayContext(play=play)
    # ansible.plugins.connection.local.Connection
    connection: Connection = connection_loader.get('local', play_context, os.devnull)

    data = {
        "name": "spire-agent-local1",
        "io_patricecongo.spire.spire_agent": {
            "state": expected_state.state.name,
            "substate_service_installation": expected_state.substate_service_installation_name(),
            "substate_service_status": expected_state.substate_service_status_name(),
            "substate_agent_registered": expected_state.substate_agent_registered_name(),

            "spire_server_host": "spire_server",
            "spire_server_install_dir": server_runner.dir_install,
            "spire_server_registration_uds_path": server_runner.registration_uds_path,
            "spire_server_address": server_runner.bind_address,
            "spire_server_port": server_runner.bind_port,

            "spire_agent_config_dir": agent_runner.dir_config,
            "spire_agent_data_dir": agent_runner.dir_data,
            "spire_agent_install_dir": agent_runner.dir_install,
            "spire_agent_service_dir": agent_runner.service.install_dir,
            "spire_agent_log_dir": agent_runner.dir_log,
            "spire_agent_install_file_owner": None,
            "spire_agent_install_dir_mode": file_modes.mode_dir,
            "spire_agent_install_file_mode": file_modes.mode_file_not_exe, # "u=rw,g=rw",
            "spire_agent_install_file_mode_exe": file_modes.mode_file_exe, # "u=xrw,g=xr,o=xr",
            "spire_agent_version": test_data.spire_version,
            "spire_agent_additional_spiffe_id": agent_runner.additional_spiffe_id,
            "spire_agent_join_token_ttl": agent_runner.join_token_ttl,
            "spire_agent_log_level": "DEBUG",
            "spire_agent_trust_domain": server_runner.trust_domain,
            "spire_agent_socket_path":  agent_runner.socket_path,
            "spire_agent_service_name": agent_runner.service.service_name,
            "spire_agent_service_scope": "user",
            "spire_agent_healthiness_probe_timeout_seconds": 5,
            "spire_download_url": server_runner.url_dist_tar_gz(test_data.spire_version),
        }
    }

    task: Task = Task.load(data=data,
                           variable_manager=var_manager,
                           loader=data_loader)

    all_vars = var_manager.get_vars(play=play, task=task,
                                    host=inventory.get_host("localhost"))

    templar = Templar(loader=data_loader,
                      shared_loader_obj=plugins_loader, variables=None)

    action = spire_agent.ActionModule(
        task=task, connection=connection, play_context=play_context,
        loader=data_loader, templar=templar, shared_loader_obj=plugins_loader)
    action._low_level_execute_command = functools.partial(
                                            _low_level_execute_command,
                                            action._low_level_execute_command)

    ###
    ret = action.run(task_vars=all_vars)
    ###

    keys_to_check = [
        'changed', 'actual_state', 'actual_substate_agent_registered',
        'actual_substate_service_installation',
        'actual_substate_service_status', 'actual_spire_agent_version',
        "failed"
    ]
    assert {
        **expected_state.to_ansible_return_data(),
        **outcome_part
        } == {key: ret.get(key) for key in keys_to_check}

    agent_health_res = agent_runner.is_healthy()
    agent_srv_running_res = agent_runner.service.is_active()
    agent_srv_enabled_res = agent_runner.service.is_enabled()
    assert expected_local_probing == {
                    "healthy": agent_health_res.res,
                    "enabled": agent_srv_enabled_res.res,
                    "running": agent_srv_running_res.res
                    }, \
        {
            "ret": ret, "health": agent_health_res,
            "enabled": agent_srv_enabled_res,
            "running": agent_srv_running_res,
            "expected_local_probing": expected_local_probing
        }


if __name__ == '__main__':
    pytest.main()
