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
from ansible_collections.io_patricecongo.spire.plugins.module_utils import (
    spire_server_entry_cmd as show,
)
from testinfra.backend.base import CommandResult
from testinfra.modules.command import Command

testinfra_hosts = ["ansible://spire_server"]

def test_update_entry(host):

    cmd = " ".join(
        [   "/opt/spire/bin/spire-server", "entry", "show", "-parentID", "spiffe://example.org/myagent",
            #"-selector", "unix:user:etcd", "-selector", "unix:gid:1000",
            "-spiffeID", "spiffe://example.org/myagent/etcd"
        ]
    )


    cresult: CommandResult = host.run( cmd )
    assert cresult.succeeded, f"""Fail to run show entry:
                                cmd={cmd},
                                result={cresult}
                                """
    outcome = show.SpireServerEntryShowOutcome(cresult.rc, cresult.stdout, cresult.stderr)
    assert outcome.entries is not None and len(outcome.entries) ==1 , f"Should have had exactly one entry: {outcome}"
    entry: show.RegistrationEntry = outcome.entries[0]
    assert set(["unix:user:etcd", "unix:gid:1000", "updated:yes"]) == set( entry.get("selector") or [] )
    assert [ "node1.local1", "node1.local2", "node1.local3"] == entry.get("dns_name"), f"outcome={outcome}"
    assert "spiffe://example.org/myagent/etcd" == entry.get("spiffe_id")
