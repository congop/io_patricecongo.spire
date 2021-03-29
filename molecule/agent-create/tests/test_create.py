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
import shutil
import tempfile
from typing import Dict, Generator

import pytest
from testinfra.backend.base import CommandResult
from testinfra.host import Host
import testinfra.utils.ansible_runner

from molecule_helpers.host_utils import HostFuncsAdapter

ansible_runner = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ["MOLECULE_INVENTORY_FILE"]
)
testinfra_hosts = ansible_runner.get_hosts("spire_agent")

from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    spire_server_entry_cmd,
)
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_info_cmd import (
    AgentDirs,
    SpireAgentInfo,
)

import test_data


@pytest.fixture
def agent_data_dir_local() -> Generator[str, None, None]:
    data_dir_local = tempfile.mkdtemp(prefix="spire-agent-data-dir-local")
    try:
        yield data_dir_local
    finally:
        shutil.rmtree(data_dir_local)

"""Role testing files using testinfra."""


def test_agent_created(host:Host, agent_data_dir_local:str) -> None:
    host_funcs = HostFuncsAdapter(host)

    print(f"Test Infra Host: {host}")
    # copying data to local machine because certificates requires
    # files to be local
    host_funcs.docker_copy_agent_svid_der(agent_data_dir_local)
    dirs = AgentDirs(
        config_dir="/etc/spire-agent",
        data_dir=agent_data_dir_local,
        install_dir="/opt/spire-agent",
        service_name="spire_agent",
        log_dir="/var/log/spire",
        service_dir="/etc/systemd/system",
    )
    agent_info = SpireAgentInfo(
                        run_command=host_funcs.run_command,
                        log_func=host_funcs.no_log,
                        dirs=dirs,
                        service_scope="system",
                        socket_path="/tmp/agent.sock",
                        expected_version=test_data.spire_version,
                        file_exists_func=host_funcs.file_exists
    )
    print(f"agent_info:{agent_info}")
    assert ("agent-installed", *agent_info.is_agent_installed()) == ("agent-installed",True, None) \
            and ("service-installed", *agent_info.is_service_installed()) == ("service-installed",True, None) \
            and ("service-enabled", *agent_info.is_service_enabled()) == ("service-enabled",True, None) \
            and ("service-running", *agent_info.is_service_running()) == ("service-running",True, None) \
            and ("agent-healthy", *agent_info.is_agent_healthy()) == ("agent-healthy",True, None) \
            and agent_info.version == (test_data.spire_version, None) \
            , ["should have been installed, enabled and healthy", agent_info]

    spire_agent_create_ansible_result: CommandResult = host.run( "cat /tmp/spire_agent_creation_result.json")
    assert spire_agent_create_ansible_result.succeeded and spire_agent_create_ansible_result.stdout
    ansible_res_json: Dict[str,str]= json.loads(spire_agent_create_ansible_result.stdout)
    print(f"ansible_res_json={ansible_res_json}")
    agent_spiffe_id_sn_and_issue = agent_info.get_agent_spiffe_id_and_sertial_number()
    assert (    ansible_res_json.get("actual_spire_agent_spiffe_id"),
                ansible_res_json.get("actual_spire_agent_serial_number"),
                ansible_res_json.get("actual_spire_agent_get_info_issue")
            ) == agent_spiffe_id_sn_and_issue

    spire_agent_service_name = "spire_agent"
    spire_agent_service_filename = f"{spire_agent_service_name}.service"
    agent_health_res: CommandResult = host.run("%s %s", dirs.path_executable, "healthcheck")
    agent_srv_running_res: CommandResult = host.run("systemctl is-active %s", spire_agent_service_filename)
    agent_srv_enabled_res: CommandResult = host.run("systemctl is-enabled %s", spire_agent_service_filename)


    assert  (agent_health_res.succeeded and "Agent is healthy" in agent_health_res.stdout) \
            and  (agent_srv_enabled_res.succeeded and "enabled" == str(agent_srv_enabled_res.stdout).strip() ) \
            and  (agent_srv_running_res.succeeded and "active" == str(agent_srv_running_res.stdout).strip() )

    spire_server_install_dir = "/opt/spire/"
    spire_service_bin_path = os.path.join(spire_server_install_dir,"bin", "spire-server")
    cmd = " ".join(
        [
            spire_service_bin_path, "entry", "show", "-parentID", agent_spiffe_id_sn_and_issue[0],
            "-selector", f"spiffe_id:{agent_spiffe_id_sn_and_issue[0]}"
        ]
    )
    host_spire_server:Host = ansible_runner.get_host("spire_server")
    print(f"host_spire_server:{host_spire_server}")
    cresult: CommandResult = host_spire_server.run( cmd )
    assert cresult.succeeded, f"""Fail to run show entry:
                                cmd={cmd},
                                result={cresult}
                                """
    outcome = spire_server_entry_cmd.SpireServerEntryShowOutcome(cresult.rc, cresult.stdout, cresult.stderr)
    assert outcome.entries is not None and len(outcome.entries) ==1 , f"Should have had exactly one entry: {outcome}"
    entry: spire_server_entry_cmd.RegistrationEntry = outcome.entries[0]
    assert "spiffe://example.org/agent/local1" == entry.get("spiffe_id")
