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
from typing import Any, Dict

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    logging,
    spire_server_entry_cmd,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd import (
    Params,
    RegistrationEntry,
    SpireServerEntryShowOutcome,
)

# from . import spire_server_entry_cmd

ANSIBLE_METADATA = {
    'metadata_version': '0.0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: spire_spiffe_id

short_description: Ensure spiffe-ID is present or absent

version_added: "0.0.1"

description:
    - "It registers a spiffe-ID or removes it using spire-server CLI"

options:
    state:
        description:
            - specifies whether the entry should be present or not
        type: str
        required: False
        default: present
        choices: [absent, present]

    identity_args:
        description:
            - this specifies what constitutes the natural key.
            - It can be used to identify the entry which correspond to the given parameters without using the entry-id
            - "node=True --> a node spiffe-id is being specified"
            - "downstream=True -> a downstream server entry is being specified"
            - "node=False and downstream=False -> a workload entry is being specified"
            - other combinations of value for node and downstream are probably an input error
        type: list
        elements: str
        default: ["spiffe_id", "parent_id", "node", "downstream", "selector"]

    admin:
        description:
            - If set, the SPIFFE ID in this entry will be granted access to the Registration API
        required: false

    # data:
    #     description:
    #         - Path to a file containing registration data in JSON format (optional).
    #     required: false

    dns_name:
        description:
            - A DNS name that will be included in SVIDs issued based on this entry, where appropriate.
            - Can be used more than once
        required: false

    downstream:
        description:
            - A boolean value that, when set, indicates that the entry describes a downstream SPIRE server
        required: false
    entry_expiry:
        description:
            - An expiry, from epoch in seconds, for the resulting registration entry to be pruned from the datastore.
            - Please note that this is a data management feature and not a security feature (optional).
        required: false
    federates_with:
        description:
            - A list of trust domain SPIFFE IDs representing the trust domains this registration entry federates with.
            - A bundle for that trust domain must already exist
        required: false
    node:
        description:
            - If set, this entry will be applied to matching nodes rather than workloads
        required: false

    parent_id:
        description:
            - The SPIFFE ID of this record's parent.
    registration_uds_path:
        description: Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        required: false
        default: /tmp/spire-registration.sock

    selector:
        description:
            - "A colon-delimited type:value selector used for attestation."
            - This parameter can be used more than once, to specify multiple selectors that must be satisfied.
        required: false

    spiffe_id:
        description:
            - The SPIFFE ID that this record represents and will be set to the SVID issued.
        required: true

    ttl:
        description:
            - A TTL, in seconds, for any SVID issued as a result of this record.
        required: False
        default: 3600

    spire_server_cmd:
        description:
            - Name of path of the spire-server command
        default: spire-server
author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
- name: "Ensure spiffe id available"
      io_patricecongo.spire.spire_spiffe_id:
        state: present
        dns_name:
          - node1.local1
          - node1.local2
          - node1.local3
        downstream: no
        identity_args:
          - spiffe_id
          - parent_id
        parent_id: spiffe://example.org/myagent
        selector:
          - unix:user:etcd
          - unix:gid:1000
          - updated:yes
        spiffe_id: spiffe://example.org/myagent/etcd
        spire_server_cmd: /opt/spire/bin/spire-server
'''

RETURN = '''
state:
    description: state
    type: str
    returned: always
'''

def _module_args() -> Dict[str, Dict[str, Any]]:
    module_args: Dict[str, Dict[str, Any]] = dict(
        # name=dict(type='str', required=True),
        # new=dict(type='bool', required=False, default=False),
        # If set, the SPIFFE ID in this entry will be granted access to the Registration API
        admin=dict(type="bool", required=False),
        # Path to a file containing registration data in JSON format (optional).
        # data=dict(type="str", required=False),
        # -dns	A DNS name that will be included in SVIDs issued based on this entry, where appropriate.
        #       Can be used more than once
        dns_name=dict(type="list", elements="str", required=False),
        # -downstream	A boolean value that, when set, indicates that the entry describes a downstream SPIRE server
        downstream=dict(type="bool", required=False),
        # -entryExpiry	An expiry, from epoch in seconds, for the resulting registration entry to be pruned from
        #               the datastore. Please note that this is a data management feature and not a security
        #               feature (optional).
        entry_expiry=dict(type="str", required=False),
        # -federatesWith	A list of trust domain SPIFFE IDs representing the trust domains this registration entry
        #                   federates with. A bundle for that trust domain must already exist
        federates_with=dict(type="str", required=False),
        # -node	If set, this entry will be applied to matching nodes rather than workloads
        node=dict(type="str", required=False),
        # -parentID	The SPIFFE ID of this record's parent.
        parent_id=dict(type="str", required=False),
        # -registrationUDSPath Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        registration_uds_path=dict(type="str", required=False),
        # -selector	A colon-delimited type:value selector used for attestation. This parameter can be used more
        #           than once, to specify multiple selectors that must be satisfied.
        selector=dict(type="list", elements="str", required=False),
        # -spiffeID	The SPIFFE ID that this record represents and will be set to the SVID issued.
        spiffe_id=dict(type="str", required=False),
        # -ttl	A TTL, in seconds, for any SVID issued as a result of this record.	3600
        ttl=dict(type="int", required=False),
        spire_server_cmd=dict(type=str, required=False,
                              default="spire-server"),
        state=dict(default='present', choices=['absent', 'present']),
        # this specifies what constitutes the natural key.
        # It can be used to identify the entry which correspond to the given parameters without using the entry-id
        # node=True --> a node spiffe-id is being specified
        # downstream=True -> a downstream server entry is being specified
        # node=False and downstream=False -> a workload entry is being specified
        # other combinations of value for node and downstream are probably an input error
        identity_args=dict(type="list", elements="str",
                           default=["spiffe_id", "parent_id", "node", "downstream", "selector"])
    )
    return module_args

def run_module() -> None:
    module_args = _module_args()

    result = dict(
        state='absent',
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params: Params = Params(copy.deepcopy(module.params))
    func_run_command = functools.partial(AnsibleModule.run_command, module)
    func_log = logging.CachingLogger(module.log)

    try:
        show_outcome: SpireServerEntryShowOutcome = spire_server_entry_cmd.cmd_server_entry_show(
            func_run_command,
            func_log,
            params,
        )

        if show_outcome.exec_failed():
            msg = f"""
                    Fail to execute <entry show> cmd:
                        parse_error={show_outcome.parse_error}
                        rc={show_outcome.rc}
                        stdout={show_outcome.stdout}
                        stderr={show_outcome.stderr}
                        entries={show_outcome.entries}
                    """
            raise RuntimeError(msg)

        if show_outcome.parsing_failed():
            msg = f"""
                    Fail to parse <entry show> output:
                        parse_error={show_outcome.parse_error}
                        rc={show_outcome.rc}
                        stdout={show_outcome.stdout}
                        stderr={show_outcome.stderr}
                        entries={show_outcome.entries}
                    """
            raise RuntimeError(msg)

        # identity_params = params["identity_args"]
        actual_list = spire_server_entry_cmd.entries_having_same_identity(params, show_outcome.entries)
        if len(actual_list) > 1:
            module.fail_json(msg=f'Cannot handle more than one identified corresponding entries: {actual_list}')
        actual: RegistrationEntry = RegistrationEntry() if len(actual_list) == 0 else actual_list[0]
        need_change = spire_server_entry_cmd.need_change(params, actual)
        if need_change:
            debug_msg = f"""
                need_change={need_change}
                params={params}
                actual={actual}
                actual_list={actual_list}
                entries={show_outcome.entries}
                """
            func_log(debug_msg)

        state = module.params['state']
        result["state"] = state
        result["changed"] = need_change

        if need_change:
            if not module.check_mode:
                if state == "absent":
                    # TODO actual is entry not a Param so merging is not type safe intro actual.to_params()
                    # or params.to_entry(..) because it is the command being built
                    # so command data format is needed which is entry data
                    merged = {**actual, **params}
                    spire_server_entry_cmd.cmd_server_entry_delete(func_run_command, func_log, merged)
                if state == "present":
                    if not actual:
                        spire_server_entry_cmd.cmd_server_entry_create(func_run_command, func_log, params)
                    else:
                        # TODO actual is entry not a Param so merging is not type safe
                        merged = {**actual, **params}
                        spire_server_entry_cmd.cmd_server_entry_update(func_run_command, func_log, merged)
        result["debug_msg"] = str(func_log.messages)
        module.exit_json(**result)
    except Exception as e:
        module.fail_json(msg=f"Exception while running module:{func_log.messages}", exception=str(e))


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
