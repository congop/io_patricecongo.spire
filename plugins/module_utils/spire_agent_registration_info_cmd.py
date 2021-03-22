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
import datetime
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ansible_collections.io_patricecongo.spire.plugins.module_utils import spire_list_output_parser

from . import logging

def _dt_to_ansible_ret(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

class AgentRegistrationEntry:

    def __init__(
        self,
        spiffe_id: str,
        attestation_type: str,
        expiration_time: datetime.datetime,
        serial_number: int
    ) -> None:
        self.spiffe_id = spiffe_id
        self.attestation_type = attestation_type
        self.expiration_time = expiration_time
        self.serial_number = serial_number

    def serial_number_as_str(self) -> str:
        if self.serial_number is None:
            return None
        return str(self.serial_number)

    def to_ansible_result_registration_entry(self) -> Dict[str, Any]:
        return dict(
                spiffe_id=self.spiffe_id,
                attestation_type=self.attestation_type,
                expiration_time=_dt_to_ansible_ret(self.expiration_time),
                serial_number=self.serial_number
        )

    @staticmethod
    def from_agent_list_cmd_entry_data(entry_data: Dict[str, Union[str, List[str]]]) -> "AgentRegistrationEntry":
        issues = []
        spiffe_id, issue = AgentRegistrationEntry.get_str_value(entry_data, "Spiffe ID")
        if issue:
            issues.append(issue)
        attestation_type, issue = AgentRegistrationEntry.get_str_value(entry_data, "Attestation type")
        if issue:
            issues.append(issue)
        expiration_time, issue = AgentRegistrationEntry.get_date_value(entry_data, "Expiration time")
        if issue:
            issues.append(issue)
        serial_number, issue = AgentRegistrationEntry.get_int_value(entry_data, "Serial number")
        if issue:
            issues.append(issue)
        if issues:
            msg = f"""Error while injecting  entry data:
                issues:{issues}
                entry_data:{entry_data}
            """
            raise ValueError(msg)
        return AgentRegistrationEntry(spiffe_id, attestation_type, expiration_time, serial_number)

    @staticmethod
    def from_ansible_result_registration_entry(result_data: Dict[str, Any]) -> "AgentRegistrationEntry":
        expiration_time_str = result_data.get("expiration_time")
        expiration_time = datetime.datetime.strptime(expiration_time_str, "%Y-%m-%dT%H:%M:%S%z")
        return AgentRegistrationEntry(
                spiffe_id=result_data.get("spiffe_id"),
                attestation_type=result_data.get("attestation_type"),
                expiration_time=expiration_time,
                serial_number=result_data.get("serial_number")
        )

    @staticmethod
    def get_str_value(entry_data: Dict[str, Union[str, List[str]]], key: str) -> Tuple[str, str]:
        value = entry_data.get(key)
        if not isinstance(value, str):
            return None, f"entry_data[{key}]={value} - value must be a string, but is a {type(value)}"
        return value, None

    # TODO get ride  of the name in the spire Expiration Time, because it will likely cause some issues
    # e.g. when python does not have the same timezone installed as spire golang
    # it is anyway redundant because the %z is just the numeric equivalent of %Z
    # idea: regex matching?
    @staticmethod
    def get_date_value(entry_data: Dict[str, Union[str, List[str]]], key: str) -> Tuple[datetime.datetime, str]:
        exp_time_str, issue = AgentRegistrationEntry.get_str_value(entry_data, key)
        if exp_time_str is None:
            return None, issue
        # Expiration time   : 2020-09-22 01:07:36 +0200 CEST
        try:
            exp_time = datetime.datetime.strptime(exp_time_str, r"%Y-%m-%d %H:%M:%S %z %Z")
        except ValueError as e:
            import locale
            msg = f""" faile to parse as datetime [{key}]=>[{exp_time_str}]:
                error:{str(e)}
                {logging.get_exception_stacktrace(e)}
                LC_CTYPE: {locale.getlocale(locale.LC_CTYPE)}
                LC_TIME: {locale.getlocale(locale.LC_TIME)}
                getdefaultlocale:{locale.getdefaultlocale()}
                os.environ: {os.environ}
            """
            return None, msg
        return exp_time, None

    @staticmethod
    def parse_show_expiration_time(exp_time: str) -> datetime.datetime:
        return datetime.datetime.strptime(exp_time, r"%Y-%m-%d %H:%M:%S %z %Z")

    @staticmethod
    def get_int_value(entry_data: Dict[str, Union[str, List[str]]], key: str) -> Tuple[int, str]:
        int_str, issue = AgentRegistrationEntry.get_str_value(entry_data, key)
        if int_str is None:
            return None, issue
        # Expiration time   : 2020-09-22 01:07:36 +0200 CEST
        try:
            value = int(int_str)
        except ValueError as e:
            msg = f""" faile to parse as integer [{key}]=>{int_str}:
                error:{str(e)}
                {logging.get_exception_stacktrace(e)}
            """
            return None, msg
        return value, None


class AgentEntryDataPredicate:  # (Callable[[Dict[str,Union[str,List[str]]]], bool]):
    def __init__(
        self,
        spiffe_ids: Optional[List[str]],
        attestation_types: Optional[List[str]],
        serial_numbers: Optional[List[int]]
    ) -> None:
        self.spiffe_ids = spiffe_ids
        self.attestation_types = attestation_types
        self.serial_numbers = serial_numbers

    def __call__(self, entry_data: Dict[str, Union[str, List[str]]]) -> bool:
        if not entry_data:
            return False
        if self.spiffe_ids:
            spiffe_id, issue = AgentRegistrationEntry.get_str_value(entry_data, "Spiffe ID")
            if spiffe_id is None or spiffe_id not in self.spiffe_ids:
                return False
        if self.attestation_types:
            attestation_type, issue = AgentRegistrationEntry.get_str_value(entry_data, "Attestation type")
            if attestation_type is None or attestation_type not in self.attestation_types:
                return False
        if self.serial_numbers:
            serial_number, issue = AgentRegistrationEntry.get_int_value(entry_data, "Serial number")
            if serial_number is None or serial_number not in self.serial_numbers:
                return False
        return True


class SpireAgentRegistrationInfo:

    def __init__(
        self,
        run_command: Callable[[Any], Tuple[int, str, str]],
        log_func: Callable[[str, Optional[Dict[str, str]]], None],
        spire_server_install_dir: str,
        spire_agent_spiffe_ids: List[str],
        spire_agent_attestation_types: List[str],
        spire_agent_serial_numbers: List[int],
        spire_server_registration_uds_path: str,
    ) -> None:
        super().__init__()
        if not (run_command and log_func):
            msg = f""" spire_agent data mus all be non blank:
                run_command={run_command}
                log_func={log_func}
                spire_server_install_dir={spire_server_install_dir}
            """
            raise RuntimeError(msg)

        self.run_command: Callable[[Any], Tuple[int, str, str]] = run_command
        self.log_func = log_func
        self.executable: str = os.path.join(spire_server_install_dir, "bin", "spire-server")
        self.spire_server_registration_uds_path = spire_server_registration_uds_path
        self.spire_agent_spiffe_ids: List[str] = spire_agent_spiffe_ids
        self.spire_agent_attestation_types: List[str] = spire_agent_attestation_types
        self.spire_agent_serial_numbers: List[int] = spire_agent_serial_numbers

        self.executable_exists: bool = os.path.exists(self.executable)

    def __get_registration_uds_path_args(self) -> List[str]:
        if self.spire_server_registration_uds_path:
            return ["-registrationUDSPath", self.spire_server_registration_uds_path]
        else:
            return []

    def get_executable_path_does_not_exists_msg(self) -> str:
        return f"spire-server-executable[{self.executable}] does not exits"

    def find_registrations(self) -> List[AgentRegistrationEntry]:
        args = [self.executable, "agent", "list", *self.__get_registration_uds_path_args()]
        rc, stdout, stderr = self.run_command(args)
        if rc != 0:
            msg = f"failed to <spire-server agent list>: rc={rc} cmd={args}, stdout={stdout} stderr={stderr}"
            raise RuntimeError(msg)
        entry_data_list = spire_list_output_parser.parse_list_stdout(stdout)
        predicate = AgentEntryDataPredicate(spiffe_ids=self.spire_agent_spiffe_ids,
                                            attestation_types=self.spire_agent_attestation_types,
                                            serial_numbers=self.spire_agent_serial_numbers)
        entry_data_list_filtered = filter(predicate, entry_data_list)
        entries = [AgentRegistrationEntry.from_agent_list_cmd_entry_data(e) for e in entry_data_list_filtered]
        return entries
