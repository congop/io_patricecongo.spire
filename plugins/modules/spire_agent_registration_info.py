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
import functools
from typing import Any, Dict, List

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    logging,
    spire_agent_registration_info_cmd,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_registration_info_cmd import (
    AgentRegistrationEntry,
    SpireAgentRegistrationInfo,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd import (
    Params,
)

ANSIBLE_METADATA = {
    'metadata_version': '0.0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: spire_agent_registration_info

short_description: Returns a list of the registration entries matching the given criteria

version_added: 0.0.1

description:
    - Returns a list of the registration entries matching the given criteria
    - "avaible criteria are: spiffe-id, attestation type, agent serial number"

options:
    spire_server_install_dir:
        description:
            - the installation directory of the spire server software
            - binary is supposed to be location in ./bin/
            - e.g. /opt/spire/server
        type: str
        required: True

    spire_server_registration_uds_path:
        description:
            - Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        type: str
        required: false
        default: /tmp/spire-registration.sock

    spire_agent_spiffe_id:
        description:
            - the required value for the agent spiffe id
        type: str
        required: False

    spire_agent_attestation_type:
        description:
            - the required values for the agent attestation type
            - e.g join_token
        type: str
        required: false

    spire_agent_serial_number:
        description:
            - the required value for the serial number
        type: list
        elements: int
        required: false

author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
# Ensure spiffe-ID is available
- name: Get spire agent registration
  spire_agent_registration_info:
    spire_agent_spiffe_id: spiffe://example.org/spire/agent/join_token/a7cfae05-01e8-434b-8b77-a5005fd2dff3
    spire_agent_attestation_type: join_token
    spire_agent_serial_number: 287053125895546478511815643236708913196

'''

RETURN = '''
spire_agent_registrations:
    description:
        - list auf matching agent registration entries.
    type: list
    element: dict
    return: always
    contains:
        spiffe_id:
            description:
                - the registered spiffe id
        attestation_type:
            description:
                - the type ot he attestation used for the registratiion
        expiration_time:
            description:
                - "the expiration time  of the registration in the format 'YYY.mm.ddThh:MM.ss'"
                - "e.g. 2021-03-13T17:28:24"
        serial_number:
            description:
                - the spire agent certificate serial number
'''

def _module_args() -> Dict[str, Dict[str, Any]]:
    module_args = dict(
        spire_server_install_dir = dict(type="str", required=True),
        spire_server_registration_uds_path = dict(type="str", required=False),
        spire_agent_spiffe_id = dict(type="list", elements="str", required=False),
        spire_agent_attestation_type = dict(type="list", elements="str", required=False),
        spire_agent_serial_number = dict(type="list", elements="int", required=False),
    )
    return module_args

def run_module() -> None:
    module_args = _module_args()

    result: Dict[str, Any] = dict(
        changed=False,
    )
    # supports_check_mode=True is okay we just collecting data
    # and therefore no extra mechanism to address check_mode=true
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params: Params = Params(copy.deepcopy(module.params))
    func_run_command = functools.partial(AnsibleModule.run_command, module)
    func_log = logging.CachingLogger(module.log)

    try:
        registration_info: SpireAgentRegistrationInfo = SpireAgentRegistrationInfo(
            run_command=func_run_command,
            log_func=func_log,
            spire_server_install_dir=module.params.get("spire_server_install_dir"),
            spire_agent_spiffe_ids=module.params.get("spire_agent_spiffe_id"),
            spire_agent_attestation_types=module.params.get("spire_agent_attestation_type"),
            spire_agent_serial_numbers=module.params.get("spire_agent_serial_number"),
            spire_server_registration_uds_path=module.params.get("spire_server_registration_uds_path"),
        )

        entry_data_list: List[AgentRegistrationEntry] = registration_info.find_registrations()
        AgentRegistrationEntry.to_ansible_result_registration_entry
        result["spire_agent_registrations"] = [
            AgentRegistrationEntry.to_ansible_result_registration_entry(e)
            for e in entry_data_list
        ]

        result["debug_msg"] = str(func_log.messages)

        module.exit_json(**result)
    except Exception as e:
        module.fail_json(msg=f"Exception while running module:{func_log.messages}", exception=e)


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
