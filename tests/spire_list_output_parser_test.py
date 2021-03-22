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
from ansible_collections.io_patricecongo.spire.plugins.module_utils import spire_list_output_parser
import pytest


def test_parse_list_stdout():
    stdout = '''Found 1 entries

    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
    SPIFFE ID     : spiffe://example.org/myagent
    Parent ID     : spiffe:///0cd37c3e-76d6-4973-88bb-d8837d9ef7c4
    TTL           : default
    Selector      : spiffe_id:spiffe:///0cd37c3e-76d6-4973-88bb-d8837d9ef7c4
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
    expected = [
        {
            "Entry ID":         "99b8dd8c-fd3e-4c67-808f-d37aca1cae9b",
            "SPIFFE ID":        "spiffe://example.org/myagent",
            "Parent ID":        "spiffe:///0cd37c3e-76d6-4973-88bb-d8837d9ef7c4",
            "TTL":              "default",
            "Selector":         [
                                    "spiffe_id:spiffe:///0cd37c3e-76d6-4973-88bb-d8837d9ef7c4",
                                    "unix:gid:1000",
                                    "unix:user:etcd"
                                ],
            "DNS name":         ["api.sapone.k8s", "kubernetes", "localhost", "kubernetes.default"],
            "Downstream":       "true",
            "FederatesWith":    ["spiffe://example2.org", "spiffe://example3.org"],
            "Admin":            "true"
        }
    ]
    res = spire_list_output_parser.parse_list_stdout(
        to_parse=stdout,
        list_value_labels=["DNS name", "Selector", "FederatesWith"]
    )
    assert res == expected


if __name__ == '__main__':
    pytest.main()
