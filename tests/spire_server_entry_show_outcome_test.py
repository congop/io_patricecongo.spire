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

parent_id1 = "spiffe://example.org/spire/agent/join_token/0cd37c3e-76d6-4973-88bb-d8837d9ef7c4"
selector_parent_id1 = f"spiffe_id:{parent_id1}"
parent_id2 = "spiffe://example.org/spire/agent/join_token/0f65da68-c673-4c1e-898e-be806d4f9599"
selector_parent_id2 = f"spiffe_id:{parent_id2}"


def test_does_parse_success_outcome_with_entries():

    stdout = f'''Found 23 entries
    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
    SPIFFE ID     : spiffe://example.org/myagent
    Parent ID     : {parent_id1}
    TTL           : default
    Selector      : {selector_parent_id1}

    Entry ID      : 10c1f178-758d-45c0-bbe2-57558729b28c
    SPIFFE ID     : spiffe://example.org/myagent
    Parent ID     : {parent_id2}
    TTL           : default
    Selector      : {selector_parent_id2}


    Entry ID      : 1234-4321
    SPIFFE ID     : spiffe://example.local
    Parent ID     : spiffe://example.local/parent
    TTL           : 24564
    Selector      : spiffe_id:spiffe://example.local/spire/agent/join_token/tkkk
    '''
    outcome = show.SpireServerEntryShowOutcome(0, stdout, None)
    assert not outcome.parse_error, f"parse should have been successful: {outcome.parse_error}"
    expected_outcome = [
        {
            "entry_id": "99b8dd8c-fd3e-4c67-808f-d37aca1cae9b",
            "spiffe_id": "spiffe://example.org/myagent",
            "parent_id": parent_id1,
            "ttl": "default",
            "selector": [selector_parent_id1]
        },
        {
            "entry_id": "10c1f178-758d-45c0-bbe2-57558729b28c",
            "spiffe_id": "spiffe://example.org/myagent",
            "parent_id": parent_id2,
            "ttl": "default",
            "selector": [selector_parent_id2]
        },
        {
            "entry_id": "1234-4321",
            "spiffe_id": "spiffe://example.local",
            "parent_id": "spiffe://example.local/parent",
            "ttl": "24564",
            "selector": ["spiffe_id:spiffe://example.local/spire/agent/join_token/tkkk"]
        }
    ]
    assert expected_outcome == outcome.entries


def test_can_parse_fullfleged_entrdoes_parse_success_outcome_with_entries():
    stdout = f'''Found 1 entries
    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
    SPIFFE ID     : spiffe://example.org/myagent
    Parent ID     : {parent_id1}
    TTL           : default
    Selector      : {selector_parent_id1}
    Selector      : unix:gid:1000
    Selector      : unix:user:etcd
    DNS name      : api.sapone.k8s
    DNS name      : kubernetes
    DNS name      : localhost
    DNS name      : kubernetes.default
    Downstream    : true
    FederatesWith : spiffe://example2.org
    FederatesWith : spiffe://example3.org
    Admin         : true
    '''
    outcome = show.SpireServerEntryShowOutcome(0, stdout, "")
    assert not outcome.parse_error, f"parse should have been successful: {outcome.parse_error}"
    expected_outcome = [
        {
            "entry_id": "99b8dd8c-fd3e-4c67-808f-d37aca1cae9b",
            "spiffe_id": "spiffe://example.org/myagent",
            "parent_id": parent_id1,
            "ttl": "default",
            "selector": [selector_parent_id1, "unix:gid:1000", "unix:user:etcd"],
            "dns_name": ["api.sapone.k8s", "kubernetes", "localhost", "kubernetes.default"],
            "admin": "true",
            "downstream": "true",
            "federates_with": ["spiffe://example2.org", "spiffe://example3.org"]
        },
    ]
    assert expected_outcome == outcome.entries


def test_parse_can_handle_single_entry_found() -> None:
    stdout = """Found 1 entry
            Entry ID      : 4cba8d72-ae37-4f41-9fe7-af7edcc1cc4f
            SPIFFE ID     : spiffe://example.org/myagent/etcd
            Parent ID     : spiffe://example.org/myagent
            TTL           : 3600
            Selector      : unix:gid:1000
            Selector      : unix:user:etcd
            DNS name      : node1.local
            """
    outcome = show.SpireServerEntryShowOutcome(0, stdout, None)
    assert not outcome.parse_error, f"parse should have been successful: {outcome.parse_error}"
    expected_outcome = [
        {
            "entry_id":     "4cba8d72-ae37-4f41-9fe7-af7edcc1cc4f",
            "spiffe_id":    "spiffe://example.org/myagent/etcd",
            "parent_id":    "spiffe://example.org/myagent",
            "ttl":          "3600",
            "selector":     ["unix:gid:1000", "unix:user:etcd"],
            "dns_name":     ["node1.local"]
        }
    ]
    assert expected_outcome == outcome.entries


if __name__ == '__main__':
    import pytest
    pytest.main()
