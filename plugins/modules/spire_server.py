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

import shutil
from typing import Any, Dict

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_info_cmd import(
    SpireServerInfo,
    ServerDirs,
    ServerStateSnapshot
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    healthchecks,
    logging,
    spire_server_info_cmd,
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
    StateOfServer,
    SubStateServiceInstallation,
    SubStateServiceStatus,
)

ANSIBLE_METADATA = {
    'metadata_version': '0.0.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: spire_server

short_description: provisions a spire-server

version_added: "0.0.1"

description:
    - "It creates and registers or removes a spire server"

options:

    state:
        description:
            - basic state of the spire server
        required: false
        default: "present"
        choices: [present, absent]

    substate_service_installation:
        description:
            - state of the server service installation
        required: false
        default: enabled
        choices: [not_installed, installed, enabled]

    substate_service_status:
        description:
            - state ot the server service
        required: false
        deafult: healthy
        choices: [stopped, started, healthy]

    spire_server_registration_uds_path:
        description: Path to the SPIRE server registration api socket /tmp/spire-registration.sock
        required: false
        default: /tmp/spire-registration.sock

    spire_server_address:
        description:
            - IP bind address or dns name of the spire server
        required: true

    spire_server_port:
        description:
            - the port of the spire server
        required: true

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

    spire_server_service_dir:
        description:
            - absolute path of the directory to install the spire agent systemd service file
            - must match scope
            - e.g. "/etc/systemd/system" for system scope
            - e.g. ${HOME}/.config/systemd/user/ for user scope
        required: False

    spire_server_install_file_owner:
        description:
            - owner for the installed files
            - the effective ansible user for this task, if ommited
            - e.g. "root"
        required: false

    spire_server_install_dir_mode:
        description:
            - mode for installed dir
            - e.g. "u=xrw,g=xr"
        required: false
        default: "u=xrw,g=xr"

    spire_server_install_file_mode:
        description:
            - mode for installed files
            - e.g. "u=xrw,g=xr"
        required: false
        default: "u=xrw,g=xr"

    spire_server_install_file_mode_exe:
        description:
            - mode for installed executable files
            - e.g. "u=xrw,g=xr,o=xr"
        required: false
        default: "u=xrw,g=xr,o=xr"

    spire_server_version:
        description:
            - version of the spire server binary
            - e.g. "0.10.0"
        required: true

    spire_server_log_level:
        description:
            - server log level
        required: false
        default: "INFO"
        choices: [DEBUG, INFO, WARN, ERROR]

    spire_server_log_format:
        description:
            - server log level
        required: false
        default: "text"
        choices: [text, json]

    spire_server_log_dir:
        description:
            - the target directory for spire_server logging
        required: True

    spire_server_trust_domain:
        description:
            - the server spiffe trust domain
            - e.g. "example.org"
        required: true

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

    spire_server_healthiness_probe_timeout_seconds:
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

    spire_server_plugins:
        description:
            - list of spire server plugin specifications
        required: true

    spire_server_ca_key_type:
        description:
            - The key type used for the server CA, <rsa-2048|rsa-4096|ec-p256|ec-p384>
        required: false
        default: ec-p256

    spire_server_ca_ttl:
        description:
            - The default CA/signing key TTL
            - duration format, anything arsable by golang time.ParseDuration
            - e.g. "300ms", "-1.5h" or "2h45m". Valid time units are "ns", "us" (or "µs"), "ms", "s", "m", "h"
        required: false
        default: 24h

    spire_server_ca_subject_commom_name:
        description:
            - The CommonName value of the Subject that CA certificates should use
        required: true

    spire_server_ca_subject_country:
        description:
            - Array of Country values of the Subject that CA certificates should use
        required: true

    spire_server_ca_subject_organization:
        description:
            - Array of Organization values of the Subject that CA certificates should use
        required: true

    spire_server_jwt_issuer:
        description:
            - The issuer claim used when minting JWT-SVIDs
        required: false

    spire_server_default_svid_ttl:
        description:
            - default svid ttl
            - duration format, anything arsable by golang time.ParseDuration()
            - e.g. "300ms", "1.5h" or "2h45m". Valid time units are "ns", "us" (or "µs"), "ms", "s", "m", "h"
        type: str
        required: False
        default: 1h

author:
    - Patrice Congo (@congop)
'''

EXAMPLES = '''
- name: "Ensure spire server healthy running as user spire"
  io_patricecongo.spire.spire_server:
        state: "present"
        substate_service_installation: "enabled"
        substate_service_status: "healthy"

        spire_server_address: "172.17.0.1"
        spire_server_port: 8081

        spire_server_config_dir: "/home/spire/spire-server/conf"
        spire_server_data_dir: "/home/spire/spire-server/data/"
        spire_server_install_dir: "/home/spire/spire-server/"
        #spire_server_service_dir: "/etc/systemd/system"
        spire_server_service_dir: "/home/spire/.config/systemd/user/"
        spire_server_install_file_owner: "spire"
        spire_server_install_file_mode: "u=xrw,g=xr,o=xr"
        spire_server_install_file_mode_exe: "u=xrw,g=xr,o=xr"
        spire_server_version: "0.10.1"
        spire_server_log_level: "DEBUG"
        spire_server_log_format: "text"
        spire_server_trust_domain: "example.org"
        spire_server_registration_uds_path: "/tmp/spire-registration.sock"
        spire_server_log_dir: "/home/spire/spire-server/logs"
        spire_server_service_name: "spire_server"
        spire_server_service_scope: "user"
        spire_server_healthiness_probe_timeout_seconds: 15

        spire_download_url: "file:///tmp/download/docker-spire-server/.download/spire-0.10.0-linux-x86_64-glibc.tar.gz"

        spire_server_ca_key_type: "ec-p256"
        spire_server_ca_ttl: "168h"
        spire_server_ca_subject_commom_name: "molecule_test_server_create"
        spire_server_ca_subject_country: "de"
        spire_server_ca_subject_organization: "dev"
        spire_server_jwt_issuer: "molecule_test_server_create"

        spire_server_plugins:
            - type: "DataStore"
            name: "sql"
            data:
                database_type: "sqlite3"
                connection_string: "/home/spire/spire-server/data/datastore.sqlite3"
            - type: "KeyManager"
            name: "disk"
            data:
                keys_path: "/home/spire/spire-server/data/keys.json"
            - type: "NodeAttestor"
            name: "join_token"
            data: {}
        become: yes
        become_user: "spire"
        become_method: su
        register: spire_server_creation_result
'''

RETURN = '''
actual_state:
    description: base spire server state
    type: str
    returned: always
    choices: [present, absent]

actual_substate_service_installation:
    description: spire server installation sub-state
    type: str
    returned: always
    choices: [not_installed, installled, enabled]

actual_substate_service_status:
    description: spire server service status
    type: str
    returned: always
    choices: [stopped, started, healthy]

info:
    description:
        - contains installation and runtime info about the spire server instance
        - its basically the information return by the module spire_server_info
    type: complex
    contains:
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

def _module_args() -> Dict[str, Dict[str,Any]]:
    module_args = dict(
        state=dict(type="str", required=False, default="present", choices=State.names()),
        substate_service_installation=dict(
            type="str", required=False, default="enabled",
            choices=SubStateServiceInstallation.names()),
        substate_service_status=dict(
            type="str", required=False, default="healthy",
            choices=SubStateServiceStatus.names()),

        spire_server_registration_uds_path=dict(
            type="str", required=False,
            defaults="/tmp/spire-registration.sock"),
        spire_server_address=dict(type="str", required=False, default="0.0.0.0"),
        spire_server_port=dict(type="int", required=False, default="8081"),

        spire_server_config_dir=dict(
            type="str", required=True,
            _default="/etc/spire-server"),
        spire_server_data_dir=dict(
            type="str", required=True,
            _defaults="/var/lib/spire-server-data"),
        spire_server_install_dir=dict(
            type="str", required=True,
            _defaults="/opt/spire-server"),
        spire_server_service_dir=dict(
            type="str", required=False,
            _defaults="/etc/systemd/system"),
        spire_server_install_file_owner=dict(
            type="str", required=False, _defaults="root"),
        spire_server_install_dir_mode=dict(
            type="str", required=False, defaults="u=rwx,g=rx"),
        spire_server_install_file_mode=dict(
            type="str", required=False, defaults="u=rw,g=rw"),
        spire_server_install_file_mode_exe=dict(
            type="str", required=False, defaults="u=xrw,g=xr,o=xr"),

        spire_server_version=dict(type="str", required=True),
        spire_server_log_level=dict(
            type="str", required=False, choices=["DEBUG", "INFO"], defaults="INFO"),
        spire_server_log_dir=dict(
            type="str", required=True, _defaults="/var/log/spire-server"),
        spire_server_log_format=dict(
            type="str", required=False, choices=["text", "json"], defaults="text"),

        spire_server_trust_domain=dict(type="str", required=True),
        spire_server_service_name=dict(
            type="str", required=False, defaults="spire_server"),
        spire_server_service_scope=dict(
            type="str", required=False, __defaults="system"),
        spire_server_healthiness_probe_timeout_seconds=dict(
            type="int", required=True, defaults=5),

        spire_server_plugins=dict(
            type="list", elements="json", required=True, defaults=5),

        spire_download_url=dict(type="str", required=True),

        spire_server_ca_key_type=dict(
            type="str", required=True,
            choices=["rsa-2048", "rsa-4096", "ec-p256", "ec-p384"],
            defaults="ec-p256",),
        spire_server_ca_ttl=dict(
            type="str", required=False,
            defaults="24h",),
        spire_server_default_svid_ttl=dict(
            type="str", required=False,
            defaults="1h",),
        spire_server_ca_subject_commom_name=dict(
            type="str", required=True,),
        spire_server_ca_subject_country=dict(
            type="str", required=True,),
        spire_server_ca_subject_organization=dict(
            type="str", required=True,),
        spire_server_jwt_issuer=dict(
            type="str", required=False,),

    )
    return module_args

def _server_info_from_module_params(
    run_command: RunCommand,
    log_func: logging.CachingLogger,
    server_dirs: ServerDirs,
    params: Params
) -> SpireServerInfo:
    server_info: SpireServerInfo = SpireServerInfo(
            run_command=run_command,
            log_func=log_func,
            server_dirs=server_dirs,
            registration_uds_path=params["spire_server_registration_uds_path"],
            service_name=params["spire_server_service_name"],
            service_scope=params["spire_server_service_scope"],
            expected_version=params["spire_server_version"]
        )
    return server_info

def run_module() -> None:
    module_args = _module_args()

    # TODO check if check_mode does make any sense?
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params: Params = Params(copy.deepcopy(module.params))
    func_run_command = RunCommand(module)
    func_log = logging.CachingLogger(module.log)

    try:
        server_dirs = ServerDirs.from_ansible_src(value_lookup_func=module.params.get)
        server_info: SpireServerInfo = _server_info_from_module_params(
            run_command=func_run_command,
            log_func=func_log,
            server_dirs=server_dirs,
            params=params
        )
        state_snapshot = ServerStateSnapshot(server_info)
        current_state: StateOfServer = state_snapshot.get_state_of_server()
        expected_state: StateOfServer = StateOfServer.from_task_args(params)
        changed = False
        func_log(f"state-of-server: actual={current_state}, expected={expected_state}")
        if expected_state.need_change(current_state):
            changed = True
            func_log(f"Change expected:state={expected_state.state}")
            service = systemd.SpireComponentService(
                service_name=module.params["spire_server_service_name"],
                scope=systemd.Scope.by_name(module.params["spire_server_service_scope"]),
                run_command=func_run_command,
                log_func=func_log
            )
            if expected_state.state == State.absent:
                service.teardown_service()
                dir_keys = [
                    "spire_server_config_dir",
                    "spire_server_data_dir",
                    "spire_server_install_dir",
                    # "spire_server_service_dir"
                ]
                for dir_key in dir_keys:
                    dir_value: str = module.params.get(dir_key)
                    if dir_keys is not None and not dir_value.isspace():
                        shutil.rmtree(dir_value.strip())
                log_dir: str = module.params.get("spire_server_log_dir")
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
                        server_info.assert_spire_component_and_srv_are_installed()
                        if expected_state.substate_service_installation == SubStateServiceInstallation.enabled:
                            service.enable()
                        if expected_state.substate_service_status == SubStateServiceStatus.stopped:
                            service.stop()
                        else:  # started or healthy
                            service.start()
                            if expected_state.substate_service_status == SubStateServiceStatus.healthy:
                                timeout = module.params["spire_server_healthiness_probe_timeout_seconds"]
                                healthcheck = healthchecks.CheckServer(
                                    run_command=func_run_command,
                                    file_spire_server_bin=server_info.get_executable_path(),
                                    readiness_probe_timeout_seconds=timeout,
                                    registration_uds_path=module.params["spire_server_registration_uds_path"]
                                )
                                healthcheck.wait_for_readiness()

            server_info = _server_info_from_module_params(
                run_command=func_run_command,
                log_func=func_log,
                server_dirs=server_dirs,
                params=params
            )
            state_snapshot = spire_server_info_cmd.ServerStateSnapshot(server_info)
        current_state = state_snapshot.get_state_of_server()
        func_log(f"issues = {state_snapshot.get_all_issues()}")
        result = {
            "changed": changed,
            **current_state.to_ansible_return_data(),
            "info": state_snapshot.to_ansible_result(),
            "debug_msg": func_log.messages,
        }
        module.exit_json(**result)
    except Exception as e:
        print(func_log.messages)
        module.fail_json(
            msg=f"Exception while running module:{str(e)}",
            exception=e,
            debug_msg=func_log.messages,
        )


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
