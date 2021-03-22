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
from typing import Dict, List, Union

from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd import (
    Params,
    RegistrationEntry,
    entries_having_same_identity,
    need_change,
)
import pytest


@pytest.mark.parametrize(
    "test_case, params, entries, expected",
    [
        (
            "",
            {'dns_name': ['node1.local'], 'downstream': False,
             'parent_id': 'spiffe://example.org/myagent',
             'selector': ['unix:user:etcd', 'unix:gid:1000'],
             'spiffe_id': 'spiffe://example.org/myagent/etcd', 'spire_server_cmd': '/spire-server',
             'state': 'present', 'identity_args': ['spiffe_id', 'parent_id', 'node', 'downstream', 'selector'],
             'admin': None, 'entry_expiry': None, 'federates_With': None,
             'node': None, 'registration_uds_path': None, 'ttl': None
             },
            [
                {'entry_id': 'f505f750-3511-46ab-a4a7-87cdecbe4c4b',
                 'spiffe_id': 'spiffe://example.org/myagent/etcd',
                 'parent_id': 'spiffe://example.org/myagent', 'ttl': '3600',
                 'selector': ['unix:gid:1000', 'unix:user:etcd'],
                 'dns_name': ['node1.local']
                 }
            ],
            [
                {'entry_id': 'f505f750-3511-46ab-a4a7-87cdecbe4c4b',
                 'spiffe_id': 'spiffe://example.org/myagent/etcd',
                 'parent_id': 'spiffe://example.org/myagent', 'ttl': '3600',
                 'selector': ['unix:gid:1000', 'unix:user:etcd'],
                 'dns_name': ['node1.local']
                 }
            ]
        )
    ]
)
def test_entries_having_same_identity(
    test_case: str,
    params: Dict[str, Union[List[str], str, bool]],
    entries: List[RegistrationEntry],
    expected: List[RegistrationEntry]
) -> None:
    actual = entries_having_same_identity(Params(params), entries)
    assert actual == expected, f"case failed: {test_case}"


@pytest.mark.parametrize(
    "test_case, params, entry, expected",
    [
        (
            "no_change_needed_if_all_match",

            {'dns_name': ['node1.local'], 'downstream': False,
             'parent_id': 'spiffe://example.org/myagent',
             'selector': ['unix:user:etcd', 'unix:gid:1000'],
             'spiffe_id': 'spiffe://example.org/myagent/etcd',
             'spire_server_cmd': '/spire-server', 'state': 'present',
             'identity_args': ['spiffe_id', 'parent_id', 'node', 'downstream', 'selector'],
             'admin': None, 'entry_expiry': None, 'federates_With': None, 'node': None,
             'registration_uds_path': None, 'ttl': None
             },

            {'entry_id': '4dfe4a64-e667-4692-9463-4204cd455058',
             'spiffe_id': 'spiffe://example.org/myagent/etcd',
             'parent_id': 'spiffe://example.org/myagent', 'ttl': '3600',
             'selector': ['unix:gid:1000', 'unix:user:etcd'],
             'dns_name': ['node1.local']
             },
            False
        ),
        (
            "change_needed_dns_does_not_match",

            {'dns_name': ['node1.local2', 'node1.local'], 'downstream': False,
             'parent_id': 'spiffe://example.org/myagent',
             'selector': ['unix:user:etcd', 'unix:gid:1000'],
             'spiffe_id': 'spiffe://example.org/myagent/etcd',
             'spire_server_cmd': '/spire-server', 'state': 'present',
             'identity_args': ['spiffe_id', 'parent_id', 'node', 'downstream', 'selector'],
             'admin': None, 'entry_expiry': None, 'federates_With': None, 'node': None,
             'registration_uds_path': None, 'ttl': None
             },
            {'entry_id': '4dfe4a64-e667-4692-9463-4204cd455058',
             'spiffe_id': 'spiffe://example.org/myagent/etcd',
             'parent_id': 'spiffe://example.org/myagent', 'ttl': '3600',
             'selector': ['unix:gid:1000', 'unix:user:etcd'],
             'dns_name': ['node1.local', 'node1.local2']
             },
            True
        )
    ]
)
def test_need_change(
    test_case: str, params: Dict[str, Union[List[str], str, bool]],
    entry: Dict[str, Union[List[str], str]], expected: bool
) -> None:
    actual = need_change(Params(params), RegistrationEntry(entry))
    assert actual == expected, f"case failed: {test_case}"


if __name__ == '__main__':
    pytest.main()
