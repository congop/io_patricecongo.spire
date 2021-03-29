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
import json
import os
from typing import Dict

from testinfra.backend.base import CommandResult
from testinfra.host import Host
import testinfra.utils.ansible_runner
from ansible_collections.io_patricecongo.spire.plugins.module_utils.systemd import Scope

from molecule_helpers.host_utils import HostFuncsAdapter

ansible_runner = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ["MOLECULE_INVENTORY_FILE"]
)
testinfra_hosts = ansible_runner.get_hosts("spire_server")

from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    spire_server_info_cmd,
)

import test_data


def test_server_created(host:Host) -> None:
    host_funcs = HostFuncsAdapter(host)
    print(f"Test Infra Host: {host}")
    server_dirs = spire_server_info_cmd.ServerDirs(
            config_dir="/etc/spire-server",
            data_dir="/var/lib/spire-server-data/",
            install_dir="/opt/spire-server",
            service_dir="/etc/systemd/system",
            log_dir="/var/log/spire-server",
            service_name = "spire_server"
        )
    info = spire_server_info_cmd.SpireServerInfo(
                        run_command=host_funcs.run_command,
                        log_func=host_funcs.no_log,
                        server_dirs=server_dirs,
                        service_name="spire_server",
                        service_scope=None,
                        registration_uds_path="/tmp/spire-registration.sock",
                        expected_version=test_data.spire_version,
                        file_exists_func=host_funcs.file_exists
    )
    print(f"server_info:{info}")
    assert ("server-installed", *info.is_installed()) == ("server-installed",True, None) \
            and ("service-installed", *info.is_service_installed()) == ("service-installed",True, None) \
            and ("service-enabled", *info.is_service_enabled()) == ("service-enabled",True, None) \
            and ("service-running", *info.is_service_running()) == ("service-running",True, None) \
            and ("server-healthy", *info.is_healthy()) == ("server-healthy",True, None) \
            and info.version == (test_data.spire_version, None) \
            and (info.service_scope, info.service_scope_issue) == (Scope.scope_system, None) \
            , ["should have been installed, enabled and healthy", info]

    spire_server_create_ansible_result: CommandResult = host.run("cat /tmp/spire_server_creation_result.json")
    assert spire_server_create_ansible_result.succeeded and spire_server_create_ansible_result.stdout
    ansible_res_json: Dict[str,str]= json.loads(spire_server_create_ansible_result.stdout)
    print(f"ansible_res_json={ansible_res_json}")