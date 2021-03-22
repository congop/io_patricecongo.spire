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
from typing import Any, Dict, Generator, List, NamedTuple
import unittest.mock as mm

import _pytest.monkeypatch as mp
from ansible.module_utils.basic import AnsibleModule

# XXXpylint: disable=sunresolved import,another-one
from ansible_collections.io_patricecongo.spire.plugins.modules import spire_spiffe_id
import pytest

from .ansible_module_test_utils import set_module_args

__original__init = AnsibleModule.__init__


class CmdOutcome(NamedTuple):
    rc: int
    stderr: str
    stdout: str


def is_sublist(source, target) -> bool:
    for i in range(len(source) - len(target)+1):
        if source[i:i + len(target)] == target:
            return True
    return False


class SpireServerCmdArgsPart(List[str]):
    pass


class SpireServerCmdArgsParts(List[SpireServerCmdArgsPart]):
    pass


class SpireServerCmdArgs(List[str]):
    def __contains__(self, key):
        if isinstance(key, list):
            not_list_or_none = list(filter(lambda x: not isinstance(x, (type(None), list)), key))
            if len(not_list_or_none) != 0:
                raise ValueError(f"""in operator or __contains__ support list of list|one only:
                        offending elements={not_list_or_none},
                        list={key}""")
            for elist in key:
                if elist is None:
                    continue
                if not is_sublist(self, elist):
                    return False
            return True
        return super().__contains__(key)


def pytest_assertrepr_compare(op, left, right):
    if isinstance(left, list) and isinstance(right, SpireServerCmdArgs) and op == "in":
        return [
            "All parts not in server cmd args:",
            f"""
            parts    = {left}
            cmd_args = {right}
            """
        ]


@pytest.fixture  # With stdlib
def mock_bar() -> Generator[AnsibleModule, None, None]:
    def am_init(self, argument_spec, **kwargs) -> AnsibleModule:  # (argument_spec, supports_check_mode):
        am = __original__init(self, argument_spec, **kwargs)
        self.check_mode = True
        return am

    with mm.patch.object(AnsibleModule, "__init__", am_init) as mock:
        mock.check_mode = True
        yield mock


parent_id = "spiffe://example.org/spire/agent/join_token/0f65da68-c673-4c1e-898e-be806d4f9599"
selector_for_parent_id = f"spiffe_id:{parent_id}"


@pytest.mark.parametrize(
    "test_case, check_mode, module_args,spire_server_cmd_outcome, expected, expected_run_command_args_parts",
    [
        (
            "test_state_changed_when_disired_present_but_no_entry_available",
            True,
            {
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"]
            },
            [(0, "", "")],
            {
                "state": "present",
                "changed": True
            },
            None
        ),

        (
            "test_state_unchanged_when_disired_present_and_equivalent_entry_found",
            True,
            {
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"]
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagent
                    Parent ID     : {parent_id}
                    TTL           : 1200
                    Selector      : {selector_for_parent_id}
                    """,
                ""
            ),
            ],
            {
                "state": "present",
                "changed": False
            },
            None
        ),
        (
            "test_state_unchanged_when_disired_absent_and_equivalent_entry_not_found",
            True,
            {
                "state": "absent",
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"]
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagentXXXXXXX
                    Parent ID     : {parent_id}
                    TTL           : 1200
                    Selector      : {selector_for_parent_id}
                    """,
                ""
            ),
            ],
            {
                "state": "absent",
                "changed": False
            },
            None
        ),
        (
            "test_state_changed_when_disired_absent_and_equivalent_entry_found",
            True,
            {
                "state": "absent",
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"]
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagent
                    Parent ID     : {parent_id}
                    TTL           : 1200
                    Selector      : {selector_for_parent_id}
                    """,
                ""
            ),
            ],
            {
                "state": "absent",
                "changed": True
            },
            None
        ),

        (
            "test_state_changed_entry_deleted_when_disired_absent_and_equivalent_entry_found",
            False,
            {
                "state": "absent",
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"]
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagent
                    Parent ID     : {parent_id}
                    TTL           : 1200
                    Selector      : {selector_for_parent_id}
                    """,
                ""
            ),
                (0, "", "")
            ],
            {
                "state": "absent",
                "changed": True
            },
            {
                1: [["spire-server", "entry", "delete"], ["-entryID", "99b8dd8c-fd3e-4c67-808f-d37aca1cae9b"]]
            }
        ),
        (
            "test_state_changed_entry_updated_when_disired_present_and_non_equivalent_entry_found",
            False,
            {
                "state": "present",
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id, "selecta:musica"],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"],
                "dns_name": ["https://blabla.local", "https://example.local"],
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagent
                    Parent ID     : {parent_id}
                    TTL           : 12001
                    Selector      : {selector_for_parent_id}
                    Selector      : selecta:musica
                    DNS name      : https://blabla.local
                    """,
                ""
            ),
                (0, "", "")
            ],
            {
                "state": "present",
                "changed": True
            },
            {
                1: [["spire-server", "entry", "update"],
                    ["-entryID", "99b8dd8c-fd3e-4c67-808f-d37aca1cae9b"],
                    ["-spiffeID", "spiffe://example.org/myagent"],
                    ["-parentID", parent_id],
                    ["-selector", selector_for_parent_id],
                    ["-selector", "selecta:musica"],
                    ["-dns", "https://blabla.local"],
                    ["-dns", "https://example.local"]
                    ]
            }
        ),

        (
            "test_state_changed_entry_created_when_disired_present_and_entry_found_id_not_eq",
            False,
            {
                "state": "present",
                "spiffe_id": "spiffe://example.org/myagent",
                "parent_id": parent_id,
                "ttl": "1200",
                "selector": [selector_for_parent_id, "selecta:musica"],
                "spire_server_cmd": "spire-server",
                "identity_args":["spiffe_id", "parent_id", "node", "downstream", "selector"],
                "dns_name": ["https://blabla.local", "https://example.local"],
            },
            [(
                0,
                f"""Found 23 entries
                    Entry ID      : 99b8dd8c-fd3e-4c67-808f-d37aca1cae9b
                    SPIFFE ID     : spiffe://example.org/myagentXXXIdentityNotMatchingXXX
                    Parent ID     : {parent_id}
                    TTL           : 12001
                    Selector      : {selector_for_parent_id}
                    Selector      : selecta:musica
                    DNS name      : https://blabla.local
                    """,
                ""
            ),
                (0, "", "")
            ],
            {
                "state": "present",
                "changed": True
            },
            {
                1: [["spire-server", "entry", "create"],
                    ["-spiffeID", "spiffe://example.org/myagent"],
                    ["-parentID", parent_id],
                    ["-selector", selector_for_parent_id],
                    ["-selector", "selecta:musica"],
                    ["-dns", "https://blabla.local"],
                    ["-dns", "https://example.local"]
                    ]
            }
        ),
    ],
)
def test_check_if_entry_not_present(
    monkeypatch: mp.MonkeyPatch,
    test_case: str, check_mode: bool, module_args: Dict[str, Any],
    spire_server_cmd_outcome: List[CmdOutcome],
    expected: Dict[str, Any], expected_run_command_args_parts: Dict[int, List[List[str]]]
) -> None:
    result = {}
    actual_args_list: List[SpireServerCmdArgs] = []

    def mock_run_command(ansiblemodule, args: List[str]):
        # return 0, "xxxxx", ""
        nonlocal spire_server_cmd_outcome
        if len(spire_server_cmd_outcome) == 0:
            return 255, "", "No mock outcome available"
        actual_args_list.append(SpireServerCmdArgs(args))
        return spire_server_cmd_outcome.pop(0)

    def am_init2(self: AnsibleModule, argument_spec, **kwargs) -> None:
        __original__init(self, argument_spec, **kwargs)
        nonlocal check_mode
        self.check_mode = check_mode
        return

    def exit_json(self, **kwargs) -> None:
        nonlocal result
        result = dict(kwargs)
        pass

    monkeypatch.setattr(AnsibleModule, "run_command", mock_run_command)
    monkeypatch.setattr(AnsibleModule, "__init__", am_init2)
    monkeypatch.setattr(AnsibleModule, "exit_json", exit_json)

    set_module_args(module_args)
    spire_spiffe_id.main()
    if "debug_msg" in result:
        del result["debug_msg"]
    assert expected == result, f"case failed: {test_case}"

    if expected_run_command_args_parts is not None:
        for index, parts in expected_run_command_args_parts.items():
            if index >= len(actual_args_list):
                pytest.fail(f"index out of range:{(index,parts)} \n\tlist={actual_args_list}")
            args = actual_args_list[index]
            # Wont catch following constellation
            # args: ...,'-selector', 'unix:user:etcd',
            #       '-selector', 'unix:gid:1000',
            #       '-selector', ['unix:user:etcd', 'unix:gid:1000'],...
            # but only checking for ['-selector', 'unix:user:etcd'],
            #                       ['-selector', 'unix:gid:1000']
            # TODO map args to dict(str:[str],bool:[], list:[str,str]) than check
            assert parts in args

    pass


if __name__ == '__main__':
    import pytest
    pytest.main()
