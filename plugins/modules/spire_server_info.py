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
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.ansible_module_cmd import RunCommand
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_info_cmd import (
    ServerStateSnapshot,
    SpireServerInfo,
    ServerDirs
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
module: spire_server_info

short_description: Gather info about a spire-server installation

version_added: "0.0.1"

description:
    - "Gather info about a spire-server installation"

options:
    spire_server_config_dir:
        description:
            - directory to hold the spire server configuration
            - e.g. "/etc/spire-server"
        required: True

    spire_server_data_dir:
        description:
            - directorsy to hold the spire agent data
            - e.g. "/var/lib/spire-server/data/server"
        required: True

    spire_server_install_dir:
        description:
            - installation directory for spire server directories
            - e.g. "/opt/spire-server/"
        required: True

    spire_server_log_dir:
        description:
            - the target directory for spire_server logging
        required: True

    spire_server_service_dir:
        description:
            - absolute path of the directory to install the spire agent systemd service file
            - must match scope
            - e.g. "/etc/systemd/system" for system scope
            - e.g. ${HOME}/.config/systemd/user/ for user scope
        required: False

    spire_server_registration_uds_path:
        description: Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        required: false
        default: /tmp/spire-registration.sock

    spire_server_service_name:
        description:
            - systemd service name for the spire server
        required: false
        default: spire_server

    spire_server_service_scope:
        description:
            - the scope of the systemd service
        required: True
        choices: [user, system]

author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
- name: "Get info about spire server"
  io_patricecongo.spire.spire_server_info:
        spire_server_config_dir: "/home/spire/spire-server/conf"
        spire_server_data_dir: "/home/spire/spire-server/data/"
        spire_server_install_dir: "/home/spire/spire-server/"
        spire_server_service_dir: "/home/spire/.config/systemd/user/"
        spire_server_registration_uds_path: "/tmp/spire-registration.sock"
        spire_server_log_dir: "/home/spire/spire-server/logs"
        spire_server_service_name: "spire_server"
        spire_server_service_scope: "user"
'''

RETURN = '''
spire_server_installed:
    description:
        - True is spire server is installed false otherwise
    returned: success
    type: bool
spire_server_installed_issue:
    description:
        - Any issue which prevented the detection of server installed state
    returned: success
    type: str
spire_server_version:
    description:
        - the spire server version
    returned: success
    type: str
spire_server_version_issue:
    description:
        - Any issue which prevented the detection of server version
    returned: success
    type: str
spire_server_executable_path:
    description:
        - the spire server executable  path
    returned: success
    type: str
spire_server_trust_domain_id:
    description:
        - the spire server trust domain id
    returned: success
    type: str
spire_server_trust_domain_id_issue:
    description:
        - Any issue which prevented the detection of the server trust domain id
    returned: success
    type: str
spire_server_is_healthy:
    description:
        - True if the spire server is healthy, False otherwise
    returned: success
    type: bool
spire_server_is_healthy_issue:
    description:
        - Any issue which prevented the detection of the server health
    returned: success
    type: str
spire_server_service_scope:
    description:
        - the actual spire server systemd service scope
    returned: success
    type: str
    choices: [system, user, global]
spire_server_service_scope_issue:
    description:
        - Any issue which prevented the detection of the spire server systemd service scope
    returned: success
    type: str
spire_server_service_installed:
    description:
        - True if the spire server systemd service is installed, False otherwise
    returned: success
    type: bool
spire_server_service_installed_issue:
    description:
        - Any issue which prevented the detection of the server systemd service installation state
    returned: success
    type: str
spire_server_service_running:
    description:
        - True if the spire server systemd service is installed, False otherwise
    returned: success
    type: bool
spire_server_service_running_issue:
    description:
        - Any issue which prevented the detection of server systemd service running state
    returned: success
    type: str
spire_server_service_enabled:
    description:
        - True if the spire server systemd service is enable, False  otherwise
    returned: success
    type: str
spire_server_service_enabled_issue:
    description:
        - Any issue which prevented the detection of the spire server systemd service enabled
    returned: success
    type: str
spire_server_hexdigest_service_file:
    description:
        - the digest  of the spire server systemd service file
    returned: success
    type: str
spire_server_hexdigest_service_file_issue:
    description:
        - Any issue which prevented the computation of the spire server systemd service file
    returned: success
    type: str
spire_server_hexdigest_config_file:
    description:
        - the digest of the spire server configuration file
    returned: success
    type: str
spire_server_hexdigest_config_file_issue:
    description:
        - Any issue which prevented the computation of the spire server configuration file
    returned: success
    type: str
spire_server_file_stats:
    description:
        - holds file state about file and directories of interest
        - basically files which change, should trigger reconciliation
        - e.g. for install dir, config dir, data dir,
    returned: success
    type: complex
'''

def _module_args() -> Dict[str, Dict[str, Any]]:
    module_args = dict(
        spire_server_config_dir = dict(type="str", required=False, default="/etc/spire-agent"),
        spire_server_data_dir = dict(type="str", required=False, defaults="/var/lib/spire-agent/data/agent"),
        spire_server_install_dir = dict(type="str", required=False, defaults="/opt/spire"),
        spire_server_log_dir = dict(type="str", required=False, defaults="/var/log"),
        spire_server_service_dir = dict(type="str", required=True),
        spire_server_registration_uds_path = dict(type="str", required=False, defaults="/tmp/spire-registration.sock"),
        spire_server_service_name = dict(type="str", required=False, defaults="spire_agent"),
        spire_server_service_scope = dict(type="str", required=False, __defaults="system"),
    )
    return module_args

def run_module() -> None:

    module_args = _module_args()

    # supports_check_mode=True we  just collecting info
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    func_run_command = RunCommand(module)

    func_log = logging.CachingLogger(module.log)

    try:
        server_dirs = ServerDirs.from_ansible_src(module.params.get)
        func_log(f"server_dirs:{server_dirs.__dict__}")
        print(f"server_dirs:{server_dirs.__dict__}")
        server_info: SpireServerInfo = SpireServerInfo(
            run_command = func_run_command,
            log_func = func_log,
            server_dirs=server_dirs,
            registration_uds_path= module.params["spire_server_registration_uds_path"],
            service_name = module.params["spire_server_service_name"],
            service_scope = module.params["spire_server_service_scope"],
        )
        state_snapshot: ServerStateSnapshot = ServerStateSnapshot(server_info)
        result = {
            "changed": False,
            **state_snapshot.to_ansible_result(),
            "debug_msg": str(func_log.messages)
        }

        module.exit_json(**result)
    except Exception as e:
        module.fail_json(
            f"Exception while running module:{func_log.messages}",
            exception=e,
            debug_msg=str(func_log.messages))


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
