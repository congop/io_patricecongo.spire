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
from typing import Any, Dict, List, NamedTuple

import _pytest.monkeypatch as mp
from ansible.module_utils.basic import AnsibleModule
import datetime
from dateutil import tz

# import set_module_args
# pylint: disable=sunresolved import,another-one
from ansible_collections.io_patricecongo.spire.plugins.modules import spire_agent_registration_info
from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_agent_registration_info_cmd import(
    _dt_to_ansible_ret
)
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
def _2020_09_22T01h07_36_CEST() -> datetime.datetime:
    de_tz = tz.gettz("Europe/Berlin")
    #2020-09-22 01:07:36 +0200 CEST
    d = datetime.datetime(2020, 9, 22, 1, 7, 36, tzinfo=de_tz)
    ltz = tz.tzlocal()
    ldate = d.astimezone(ltz)
    return ldate

def exp_date_str() -> str:
    d = _2020_09_22T01h07_36_CEST()
    dstr = d.strftime("%Y-%m-%d %H:%M:%S %z %Z")
    return dstr

@pytest.mark.parametrize(
    "test_case, module_args, spire_server_cmd_outcome, expected, expected_run_command_args_parts",
    [
        (
            "test_return_empty_list_if_no_entry_found",
            {
                "spire_agent_spiffe_id": "spiffe://example.org/myagent",
                "spire_agent_attestation_type": "join_token",
                "spire_agent_serial_number": 11223344556677889900,
                "spire_server_install_dir": "/tmp/blabla/bloblo",
                "spire_server_registration_uds_path": "/temp/blabla/comcom/channel.sockx",
            },
            [(0, "", "")],
            {
                "changed": False,
                "spire_agent_registrations": [],
            },
            None
        ),
        (
            "test_return_matching_found_entries",
            {
                "spire_agent_spiffe_id":
                    "spiffe://example.org/spire/agent/join_token/a7cfae05-01e8-434b-8b77-a5005fd2dff3",
                "spire_agent_attestation_type": "join_token",
                "spire_agent_serial_number": 41162198570021778854432230976370801677,
                "spire_server_install_dir": "/tmp/blabla/bloblo",
                "spire_server_registration_uds_path": "/temp/blabla/comcom/channel.sockx",
            },
            #2020-09-22 01:07:36 +0200 CEST
            #2020-09-22 16:16:37 +0200 CEST
            [(
                0,
                f"""Found 2 xyz
                Spiffe ID         : spiffe://example.org/spire/agent/join_token/a7cfae05-01e8-434b-8b77-a5005fd2dff3
                Attestation type  : join_token
                Expiration time   : {exp_date_str()}
                Serial number     : 41162198570021778854432230976370801677

                Spiffe ID         : spiffe://example.org/spire/agent/join_token/7d505a7b-e57b-4752-8bb0-d47704fdcb94
                Attestation type  : join_token
                Expiration time   : {exp_date_str()}
                Serial number     : 287053125895546478511815643236708913196
                """,
                ""
            )],
            {
                "changed": False,
                "spire_agent_registrations": [
                    {
                        "spiffe_id": "spiffe://example.org/spire/agent/join_token/a7cfae05-01e8-434b-8b77-a5005fd2dff3",
                        "attestation_type": "join_token",
                        "expiration_time": _dt_to_ansible_ret(_2020_09_22T01h07_36_CEST()), # "2020-09-22T01:07:36+0200",
                        "serial_number": 41162198570021778854432230976370801677
                    }
                ],
            },
            None
        ),
    ],
)
def test_module_spire_agent_registration_info(
    monkeypatch: mp.MonkeyPatch,
    test_case: str,
    module_args: Dict[str, Any],
    spire_server_cmd_outcome: List[CmdOutcome],
    expected: Dict[str, Any],
    expected_run_command_args_parts: Dict[int, List[List[str]]]
) -> None:
    result = {}
    actual_args_list: List[SpireServerCmdArgs] = []  # SpireServerCmdArgs()

    def mock_run_command(ansiblemodule, args: List[str]):
        # return 0, "xxxxx", ""
        nonlocal spire_server_cmd_outcome
        if len(spire_server_cmd_outcome) == 0:
            return 255, "", "No mock outcome available"
        actual_args_list.append(SpireServerCmdArgs(args))
        return spire_server_cmd_outcome.pop(0)

    def am_init2(self: AnsibleModule, argument_spec, **kwargs) -> None:  # (argument_spec, supports_check_mode):
        __original__init(self, argument_spec, **kwargs)
        self.check_mode = False
        return

    def exit_json(self, **kwargs) -> None:
        nonlocal result
        result = dict(kwargs)
        pass

    monkeypatch.setattr(AnsibleModule, "run_command", mock_run_command)
    monkeypatch.setattr(AnsibleModule, "__init__", am_init2)
    monkeypatch.setattr(AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(AnsibleModule, "fail_json", exit_json)

    set_module_args(module_args)
    spire_agent_registration_info.main()
    if "debug_msg" in result:
        del result["debug_msg"]
    assert expected == result, f"case failed: {test_case}"

    if expected_run_command_args_parts is not None:
        for index, parts in expected_run_command_args_parts.items():
            if index >= len(actual_args_list):
                pytest.fail(f"index out of range:{(index,parts)} \n\tlist={actual_args_list}")
            args = actual_args_list[index]
            assert parts in args

    pass


if __name__ == '__main__':
    pytest.main()
