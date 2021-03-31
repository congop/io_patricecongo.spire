#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import copy
import pathlib

# https://github.com/ansible/ansible-modules-core/blob/devel/database/postgresql/postgresql_db.py
import shutil
from typing import Any, Dict

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_info_cmd import (
    AgentDirs,
    SpireAgentInfo
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    healthchecks,
    logging,
    spire_agent_info_cmd,
    systemd,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.ansible_module_cmd import (
    RunCommand,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd import (
    Params,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    State,
    StateOfAgent,
    SubStateAgentRegistered,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)

from ansible_collections.io_patricecongo.spire.plugins.module_utils.module_assertions import(
    assert_not_handling_check_mode_since_action_reponsibility
)

ANSIBLE_METADATA = {
    'metadata_version': '0.0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: spire_agent

short_description: provisions a spire-agent

version_added: "0.0.1"

description:
    - "It creates and registers or removes a spire agent"

options:
    state:
        description:
            - basic state of the spire agent
        required: false
        default: present
        choices: [present, absent]

    substate_service_installation:
        description:
            - state of the agent service installation
        required: false
        default: enabled
        choices: [not_installed, installed, enabled]

    substate_service_status:
        description:
            - state ot the agent service
        required: false
        default: healthy
        choices: [stopped, started, healthy]

    substate_agent_registered:
        description:
            - state of the agent registration
        required: false
        default: yes
        choices: [yes, no, partially]

    spire_server_install_dir:
        description:
            - installation directory of the spire server binaries
        required: true

    spire_server_registration_uds_path:
        description: Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        required: false
        default: /tmp/spire-registration.sock

    spire_server_host:
        description:
            - ansible host of the spire server
            - e.g.  "spire_server"
        required: true

    spire_server_address:
        description:
            - IP address or dns name of the spire server
        required: true

    spire_server_port:
        description:
            - the port of the spire server
        required: true

    spire_agent_config_dir:
        description:
            - directory to hold the spire agent configuration
            - e.g. "/etc/spire-agent"
        required: false
        default: "/etc/spire-agent"

    spire_agent_data_dir:
        description:
            - directorsy to hold the spire agent data
            - e.g. "/var/lib/spire-agent/data/agent"
        required: false
        default: "/var/lib/spire-agent/data/agent"

    spire_agent_install_dir:
        description:
            - installation directory for spire agent directories
            - e.g. "/opt/spire-agent/"
        required: false
        default: "/opt/spire-agent/"

    spire_agent_service_dir:
        description:
            - absolute path of the directory to install the spire agent systemd service file
            - e.g. "/etc/systemd/system"
            - e.g. "${HOME}/.config/systemd/user/"
        required: false
        default: "/etc/systemd/system"

    spire_agent_install_file_owner:
        description:
            - owner for the installed files
            - e.g. "root"
        required: false
        default: "root"

    spire_agent_install_dir_mode:
        description:
            - mode for directories
            - e.g. "u=rw,g=rw,o="
        required: false
        default: "u=rw,g=rw,o="

    spire_agent_install_file_mode:
        description:
            - mode for installed files
            - e.g. "u=xrw,g=xr,o=xr"
        required: false
        default: "u=xrw,g=xr,o=xr"

    spire_agent_install_file_mode_exe:
        description:
            - mode for installed executable files
            - e.g. "u=xrw,g=xr,o=xr"
        required: false
        default: "u=xrw,g=xr,o=xr"

    spire_agent_version:
        description:
            - version of the spire agent binary
            - e.g. "0.10.0"
        required: true

    spire_agent_additional_spiffe_id:
        description:
            - additional spiffe id to register when using join token
            - e.g. "spiffe://example.org/agent/local1"
        required: false
    spire_agent_join_token_ttl:
        description:
            - the join token ttl in seconds
            - e.g. 600
        required: false
        default: 600
    spire_agent_log_level:
        description:
            - agent log level
        required: false
        default: INFO
        choices: [DEBUG, INFO, WARNING, ERROR]
    spire_agent_trust_domain:
        description:
            - the spiffe trust domain
            - e.g. "example.org"
        required: true
    spire_agent_socket_path:
        description:
            - spire agent socket path
        required: false
        default: "/tmp/agent.sock"
    spire_agent_log_dir:
        description:
            - the target directory for spire_agent logging
        required: false
        default: /var/log/
    spire_agent_service_name:
        description:
            - systemd service name for the spire agent
        required: false
        default: spire_agent
    spire_agent_service_scope:
        description:
            - the scope of the systemd service
        required: false
        default: system
        choices: [user, system]
    spire_agent_healthiness_probe_timeout_seconds:
        description:
            - timeout for healthiness probe
        required: false
        default: 5

    spire_download_url:
        description:
            - url to download spire distribution from
            - e.g. "file:///tmp/download/docker-spire-server/.download/spire-0.10.0-linux-x86_64-glibc.tar.gz"
            - e.g. "https://github.com/spiffe/spire/releases/download/v0.10.0/spire-0.10.0-linux-x86_64-glibc.tar.gz"
        required: true
author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
- name: "spire agent installed started and registered"
      io_patricecongo.spire.spire_agent:
        state: "present"
        substate_service_installation: "enabled"
        substate_service_status: "healthy"
        substate_agent_registered: "yes"

        node_spiffe_id: "spiffe://example.org/myagent"

        spire_server_install_dir: "/opt/spire"
        spire_server_host: "spire_server"
        spire_server_address: "spire_server"
        spire_server_port: 8081

        spire_agent_config_dir: "/etc/spire-agent"
        spire_agent_data_dir: "/var/lib/spire-agent/data/agent"
        spire_agent_install_dir: "/opt/spire-agent/"
        spire_agent_service_dir: "/etc/systemd/system"
        spire_agent_install_file_owner: "root"
        spire_agent_install_file_mode: "u=rw,g=rw"
        spire_agent_install_file_mode_exe: "u=xrw,g=xr,o=xr"
        spire_agent_version: "0.10.0"
        spire_agent_additional_spiffe_id: "spiffe://example.org/agent/local1"
        spire_agent_join_token_ttl: 600
        spire_agent_log_level: "DEBUG"
        spire_agent_trust_domain: "example.org"
        spire_agent_socket_path: "/tmp/agent.sock"
        spire_agent_log_dir: spire_agent_log_dir
        spire_agent_service_name: "spire_agent"
        spire_agent_service_scope: "system"
        spire_agent_healthiness_probe_timeout_seconds: 15

        spire_download_url: "file:///tmp/download/docker-spire-server/.download/spire-0.10.0-linux-x86_64-glibc.tar.gz"

'''

RETURN = '''
actual_state:
    description: base spire agent state
    type: str
    returned: always
substate_service_installation:
    description: spire agent installation sub-state
    type: str
    returned: always
substate_service_status:
    description: spire agent service status
    type: str
    returned: always
service_started:
    description: true if spire_agent service is started
    type: bool
    returned: always
'''

def _module_args() -> Dict[str, Dict[str,Any]]:
    module_args = dict(
        state=dict(type="str", required=False, default="present", choices=State.names()),
        substate_service_installation=dict(
            type="str", required=False, default="enable",
            choices=SubStateServiceInstallation.names()),
        substate_service_status=dict(
            type="str", required=False, default="healthy",
            choices=SubStateServiceStatus.names()),
        substate_agent_registered=dict(
            type="str", required=False, default="healthy",
            choices=SubStateAgentRegistered.names()),

        spire_server_install_dir=dict(type="str", required=True),
        spire_server_registration_uds_path=dict(
            type="str", required=False,
            defaults="/tmp/spire-registration.sock"),
        spire_server_host=dict(type="str", required=True, ),
        spire_server_address=dict(type="str", required=True),
        spire_server_port=dict(type="int", required=True),

        spire_agent_config_dir=dict(
            type="str", required=False,
            default="/etc/spire-agent"),
        spire_agent_data_dir=dict(
            type="str", required=False,
            defaults="/var/lib/spire-agent/data/agent"),
        spire_agent_install_dir=dict(
            type="str", required=False, defaults="/opt/spire-agent"),
        spire_agent_service_dir=dict(
            type="str", required=False,
            defaults="/etc/systemd/system"),
        spire_agent_install_file_owner=dict(
            type="str", required=False, defaults="root"),
        spire_agent_install_dir_mode=dict(
            type="str", required=False, defaults="u=rw,g=rw,o="),
        spire_agent_install_file_mode=dict(
            type="str", required=False, defaults="u=rw,g=rw"),
        spire_agent_install_file_mode_exe=dict(
            type="str", required=False, defaults="u=xrw,g=xrw,o=xr"),

        spire_agent_version=dict(type="str", required=True),
        spire_agent_additional_spiffe_id=dict(type="str", required=True),
        spire_agent_join_token_ttl=dict(
            type="int", required=True, defaults=600),
        spire_agent_log_level=dict(
            type="str", required=False, defaults="INFO"),
        spire_agent_trust_domain=dict(type="str", required=True),
        spire_agent_socket_path=dict(
            type="str", required=False, defaults="/tmp/agent.sock"),
        spire_agent_log_dir=dict(
            type="str", required=False, defaults="/var/log"),
        spire_agent_service_name=dict(
            type="str", required=False, defaults="spire_agent"),
        spire_agent_service_scope=dict(
            type="str", required=False, __defaults="system"),
        spire_agent_healthiness_probe_timeout_seconds=dict(
            type="int", required=True, defaults=5),

        spire_download_url=dict(type="str", required=True),
    )
    return module_args


def run_module() -> None:
    module_args = _module_args()


    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params: Params = Params(copy.deepcopy(module.params))
    func_run_command = RunCommand(module)
    func_log = logging.CachingLogger(module.log)

    try:
        assert_not_handling_check_mode_since_action_reponsibility(module)

        dirs: AgentDirs = AgentDirs(
            config_dir=module.params["spire_agent_config_dir"],
            data_dir=module.params["spire_agent_data_dir"],
            log_dir=module.params["spire_agent_log_dir"],
            service_dir=module.params["spire_agent_service_dir"],
            install_dir=module.params["spire_agent_install_dir"],
            service_name=module.params["spire_agent_service_name"],
        )
        agent_info: SpireAgentInfo = SpireAgentInfo(
            run_command=func_run_command,
            log_func=func_log,
            dirs=dirs,
            socket_path=module.params["spire_agent_socket_path"],
            service_scope=module.params["spire_agent_service_scope"],
        )
        state_snapshot = spire_agent_info_cmd.AgentStateSnapshot(agent_info)
        current_state: StateOfAgent = state_snapshot.get_state_of_agent()
        expected_state: StateOfAgent = StateOfAgent.from_task_args(params)
        if expected_state.need_change(current_state):
            func_log(f"Change expected:state={expected_state.state}")
            service = systemd.SpireComponentService(
                service_name=module.params["spire_agent_service_name"],
                scope=systemd.Scope.by_name(module.params["spire_agent_service_scope"]),
                run_command=func_run_command,
                log_func=func_log
            )
            if expected_state.state == State.absent:
                service.teardown_service()
                dir_keys = [
                    "spire_agent_config_dir",
                    "spire_agent_data_dir",
                    "spire_agent_install_dir",
                    # "spire_agent_service_dir"
                ]
                for dir_key in dir_keys:
                    dir_value: str = module.params.get(dir_key)
                    if dir_keys is not None and not dir_value.isspace():
                        shutil.rmtree(dir_value.strip())
                log_dir: str = module.params.get("spire_agent_log_dir")
                if log_dir is not None and pathlib.Path(log_dir.strip()) != pathlib.Path("/var/log"):
                    shutil.rmtree(log_dir)
            else:
                if expected_state.need_srv_installation_change(current_state):
                    if SubStateServiceInstallation.not_installed == expected_state.substate_service_installation:
                        service.teardown_service()
                    else:
                        # all service related file are created by the ansible-action.
                        # we just make sure the service as been installed (file as been copied)
                        # This does not assess the runtime viability of the service
                        agent_info.assert_agent_and_srv_are_installed()
                        if expected_state.substate_service_installation == SubStateServiceInstallation.enabled:
                            service.enable()
                        if expected_state.substate_service_status == SubStateServiceStatus.stopped:
                            if expected_state.substate_agent_registered == SubStateAgentRegistered.yes:
                                # registration is a collaborative job between agent and server.
                                # we do not have access to the server from here.
                                # we however know that an healthy agent must have a valid registration
                                # So our strategy to ensure registration is to:
                                #   - starts the agent
                                #   - wait for its healthiness
                                #   - and and stop it
                                service.start()
                                timeout = module.params["spire_agent_healthiness_probe_timeout_seconds"]
                                healthcheck = healthchecks.CheckAgent(
                                    run_command=func_run_command,
                                    file_spire_agent_bin=dirs.path_executable,
                                    readiness_probe_timeout_seconds=timeout,
                                    socket_path=module.params["spire_agent_socket_path"]
                                )
                                healthcheck.wait_for_readiness()
                            service.stop()
                        else:  # started or healthy
                            service.start()
                            if expected_state.substate_service_status == SubStateServiceStatus.healthy:
                                timeout = module.params["spire_agent_healthiness_probe_timeout_seconds"]
                                healthcheck = healthchecks.CheckAgent(
                                    run_command=func_run_command,
                                    file_spire_agent_bin=dirs.path_executable,
                                    readiness_probe_timeout_seconds=timeout,
                                    socket_path=module.params["spire_agent_socket_path"]
                                )
                                healthcheck.wait_for_readiness()

        agent_info.reset_computed_base_state()
        state_snapshot = spire_agent_info_cmd.AgentStateSnapshot(agent_info)
        current_state = state_snapshot.get_state_of_agent()
        func_log(f"issues = {state_snapshot.get_issues_issues()}")
        result = {
            "changed": False,
            **current_state.to_ansible_return_data(),
            "debug_msg": func_log.messages,
        }
        module.exit_json(**result)
    except Exception as e:
        module.fail_json(
            msg=f"Exception while running module:{str(e)}",
            exception=e,
            debug_msg=func_log.messages,
        )


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
