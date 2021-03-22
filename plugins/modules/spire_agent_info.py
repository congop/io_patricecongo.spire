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

# https://github.com/ansible/ansible-modules-core/blob/devel/database/postgresql/postgresql_db.py

import copy
import functools
from typing import Any, Callable, Dict, List, Optional, Pattern, Sequence, Tuple

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    logging,
    spire_agent_info_cmd,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.ansible_module_cmd import RunCommand
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_info_cmd import (
    AgentStateSnapshot,
    SpireAgentInfo,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd import (
    Params,
    RegistrationEntry,
    SpireServerEntryShowOutcome,
)

ANSIBLE_METADATA = {
    'metadata_version': '0.0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: spire_agent_info

short_description: Gather info about a spire-agent installation

version_added: "0.0.1"

description:
    - Gather info about a spire-agent installation

options:
    spire_agent_config_dir:
        description:
            - directory that holds the agent configuration files
            - e.g. /etc/spire-agent
        type: str
        required: true
    spire_agent_data_dir:
        description:
            - the directory that hold the agent runtime data
            - e.g. /var/lib/spire-agent/data/agent
        type: str
        required: True
    spire_agent_install_dir:
        description:
            - directory which holds the agent software
            - the binary will be located at ./bin
            - e.g. /opt/spire
        type: str
        required: True
    spire_agent_socket_path:
        description:
            - path to socket file use to communicate with the agent
            - e.g.
        type: str
        required: False
        default: /tmp/agent.sock
    spire_agent_service_name:
        description:
            - expected name of the spire agent systemd service
        type: str
        required: False
        default: spire_agent
    spire_agent_service_scope:
        description:
            - expected systemd scope of the spire agent service
        type: str
        required: True
        choices: [system, user]
author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
# Ensure spiffe-ID is available
- name: Get sire agent info
    io_patricecongo.spire_agent_info:
        spire_agent_config_dir: /etc/spire-agent
        spire_agent_data_dir: /var/lib/spire/agent/data
        spire_agent_install_dir": /opt/spire-agent
        spire_agent_socket_path": /tmp/agent.sock
        spire_agent_service_name: spire_agent
        spire_agent_service_scope": system
'''

RETURN = '''
spire_agent_installed:
    description:
        - True if the agent software is installed, False otherwise
    type: bool

spire_agent_installed_issue:
    description:
        - any issue which prevented the detection of spire_agent_installed
    type: str

spire_agent_spiffe_id:
    description:
        - the spiffe-id of the spire agent
    type: str

spire_agent_spiffe_id_issue:
    description:
        - any issue which prevented the dectection of spire_agent_spiffe_id
    type: str

spire_agent_serial_number:
    description:
        - the serial number of the spire agent certificate
    type: int

spire_agent_version:
    description:
        - the version of the spire agent binary
    type: str

spire_agent_version_issue:
    description:
        - any issue which prevented the detection of  the agent version
    type: str

spire_agent_executable_path:
    description:
        - agent binary executable path
    type: str

spire_agent_trust_domain_id:
    description:
        - the trust domain id of the agent
    type: str

spire_agent_trust_domain_id_issue:
    description:
        - any issue which prevented the detection of the agent trust domain id
    type: str

spire_agent_is_healthy:
    description:
        - True if the agent is healty, False  otherwise
    type: bool

spire_agent_is_healthy_issue:
    description:
        - any issue which prevented the detection of the agent health
    type: str

spire_agent_service_scope:
    description:
        - the actual detected scope of the agent systemd service
        - which means it can differ from the task argument specification
    choices: [system, user, global]

spire_agent_service_scope_issue:
    description:
        - any issue which prevented the detection of the spire agent systemd service scope
    type: str

spire_agent_service_installed:
    description:
        - True if the aagent service is installed, False otherwise
    type: bool

spire_agent_service_installed_issue:
    description:
        - any issue which prevented the detection of the agent service installed status
    type: str

spire_agent_service_running:
    description:
        - True if the agent systemd service is running, False otherwise
    type: bool

spire_agent_service_running_issue:
    description:
        - any issue which presented the detection of th service running status
    type: str

spire_agent_service_enabled:
    description:
        - True if the agent systemd service is enabled, False otherwise
    type: bool

spire_agent_service_enabled_issue:
    description:
        - any issue which prevented the detection of the agent systemd service enabled state
    type: str

'''

def _module_args() -> Dict[str, Dict[str,Any]]:
    module_args = dict(
        spire_agent_config_dir = dict(type="str", required=True, _default="/etc/spire-agent"),
        spire_agent_data_dir = dict(type="str", required=True, _default="/var/lib/spire-agent/data/agent"),
        spire_agent_install_dir = dict(type="str", required=True, _default="/opt/spire"),
        spire_agent_socket_path = dict(type="str", required=False, default="/tmp/agent.sock"),
        spire_agent_service_name = dict(type="str", required=False, default="spire_agent"),
        spire_agent_service_scope = dict(type="str", required=True, choices=["system", "user"], __default="system"),
    )
    return module_args

def run_module() -> None:
    module_args = _module_args()

    # TODO check if check_mode does make any sens?
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params: Params = Params(copy.deepcopy(module.params))
    func_run_command = RunCommand(module)

    func_log = logging.CachingLogger(module.log)

    try:
        agent_info: SpireAgentInfo = SpireAgentInfo(
            run_command = func_run_command,
            log_func = func_log,
            config_dir = module.params["spire_agent_config_dir"],
            data_dir = module.params["spire_agent_data_dir"],
            install_dir = module.params["spire_agent_install_dir"],
            socket_path = module.params["spire_agent_socket_path"],
            service_name = module.params["spire_agent_service_name"],
            service_scope = module.params["spire_agent_service_scope"],
        )
        state_snapshot: AgentStateSnapshot = AgentStateSnapshot(agent_info)
        result = {
            "changed": False,
            **state_snapshot.to_ansible_result(),
            "debug_msg": str(func_log.messages)
        }
        module.exit_json(**result)
    except Exception as e:
        module.fail_json(msg=f"Exception while running module:{func_log.messages}", exception=e)


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
