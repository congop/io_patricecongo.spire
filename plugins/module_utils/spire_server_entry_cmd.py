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
import functools
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union, cast


class RegistrationEntry(Dict[str, Union[List[str], str]]):
    """Models a registered Node or workload.
    selectors: A list of selectors.
    parent_id: The SPIFFE ID of an entity that is authorized to attest the validity of a selector
    spiffe_id: The SPIFFE ID is a structured string used to identify a resource or
        caller. It is defined as a URI comprising a “trust domain” and an
        associated path.
    ttl: Time to live.
    federates_with: A list of federated trust domain SPIFFE IDs.
    entry_id: Entry ID
    admin: Whether or not the workload is an admin workload. Admin workloads
        can use their SVID's to authenticate with the Registration API, for
        example.
    downstream: To enable signing CA CSR in upstream spire server
    entry_expiry: Expiration of this entry, in seconds from epoch

    dns_names: DNS entries
    revision_number: Revision number is bumped every time the entry is updated
    """

    # selectors: List[str] = None
    # """The SPIFFE ID of an entity that is authorized to attest the validity of a selector"""
    # parent_id: str = None
    # spiffe_id: str = None
    # ttl: int = None
    # federates_with: List[str] = None
    # entry_id: str = None
    # admin: bool = None
    # downstream: bool = None
    # entry_expiry: int = None
    # dns_names: List[str] = None
    # revision_number: int = None

    @staticmethod
    def is_list_entry(key: str) -> bool:
        return "selector" == key or "dns_name" == key or "federates_with" == key \
                or "identity_args" == key

    @staticmethod
    def is_bool_entry(key: str) -> bool:
        return "downstream" == key or "node" == key or "admin" == key

    def contribute_to_entry_map(self, key: str, value: str) -> None:
        if value is None:
            return
        map_value = self.get(key)
        if map_value is None:
            if RegistrationEntry.is_list_entry(key):
                self[key] = [value]
            else:
                self[key] = value
        else:
            if RegistrationEntry.is_list_entry(key):
                cast(List[str], map_value).append(value)
            else:
                raise RuntimeError(
                    f"Cannot add pair[key={key}, value={value} to map, because non-list value already exists: map=>{self}")

    def get_bool(self, key:str) -> bool:
        if not RegistrationEntry.is_bool_entry(key):
            raise RuntimeError(f"key[{key} is not for a value of type boolean: dict={self}")
        value: str = cast(str, self.get(key, "False"))
        if value is None:
            value = "False"
        return "true" == value.lower()

    def get_list(self, key:str) -> List[str]:
        if not RegistrationEntry.is_list_entry(key):
            raise RuntimeError(f"key[{key} is not for a value of type boolean: dict={self}")
        value: List[str] = cast(List[str], self.get(key, []))
        if value is None:
            value = []
        return value

class Params(Dict[str, Any]):
    """ Ansible module params for registration entry"""

    def get_bool(self, key: str) -> bool:
        if not RegistrationEntry.is_bool_entry(key):
            raise RuntimeError(f"key[{key} is not of type boolean")
        value: bool = self.get(key, False)
        if value is None:
            value = False
        return value

    def get_list(self, key:str) -> List[str]:
        if not RegistrationEntry.is_list_entry(key):
            raise RuntimeError(f"key[{key}] is not for a value of type list: dict={self}")
        value: List[str] = self.get(key, [])
        if value is None:
            value = []
        return value


class SpireServerEntryShowOutcome:
    # rc: int
    # stdout: str
    # stderr: str
    # entries: List[RegistrationEntry] = None #List[Dict[str, Union(List[str], str)]] = None
    # parse_error: str# = None

    def __init__(self, rc: int, stdout: str, stderr: str) -> None:
        super().__init__()
        self.rc: int = rc
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.parse_error:  Optional[str] = None
        self.entries: List[RegistrationEntry] = []
        try:
            self.entries = self.__parse_stdout()
        except Exception as e:
            import traceback
            st = traceback.format_exception(type(e), e, e.__traceback__)
            self.parse_error = f"{e} \n\tst:{st}"
        # self.entries.append("XXXX")

    def __str__(self) -> str:
        return f"""SpireServerEntryShowOutcome[
                rc: {self.rc}
                , stdout: {self.stdout}
                , stderr: {self.stderr}
                , entries: {self.entries}
                , parse_error: {self.parse_error}
                ]
                """

    def __parse_stdout(self) -> List[RegistrationEntry]:
        label_to_key = SpireServerEntryShowOutcome.label_to_key_map()
        build_entries: List[RegistrationEntry] = []
        if self.rc != 0:
            return []
        line_nr = 1
        detected = False
        entry: RegistrationEntry
        for line in self.stdout.splitlines():
            if not detected:
                # expected format: Found 23 entries
                splits = line.split(" ")
                if 3 != len(splits):
                    line_nr = line_nr + 1
                    continue
                if not ("Found" == splits[0] and splits[2] in["entries", "entry"]):
                    line_nr = line_nr + 1
                    continue
                try:
                    nr_of_entries = int(splits[1])
                    self.entries = []
                    detected = True
                except Exception as e:
                    e_str = str(e)
                    raise ValueError(f"Bad found-entries line: error ==> {e_str} Line {line_nr} ==> {line}")
            else:
                if (not line) or line.isspace():
                    continue
                splits = line.split(":", 1)
                if 2 != len(splits):
                    raise ValueError(f"Bad line formal: Line Nr. {line_nr} --> {line}")
                label = splits[0].strip()
                value = splits[1].strip()
                key = label_to_key[label]
                if not key:
                    raise ValueError(f"Line {line_nr} <- Unknown label({label}): --> {line}")
                if "entry_id" == key:
                    # this is a new entry beginning, so start building a new one
                    # appending it to the list of entries, so that we do not need to add mechanism to
                    # detect the end of the last entry.
                    entry = RegistrationEntry()#{}
                    build_entries.append(entry)
                entry.contribute_to_entry_map(key, value)
                # parse the entry
                # format:
                # Entry ID      : 0ccd30fb-2e30-40a7-918c-a282b16ee9e0
                # SPIFFE ID     : spiffe://example.org/myagent1/k8s
                # Parent ID     : spiffe://example.org/myagent1
                # TTL           : 3600
                # Selector      : unix:gid:1000,unix:user:etcd
                # DNS name      : api.sapone.k8s
                # DNS name      : kubernetes
                pass
        return build_entries

    def exec_failed(self) -> bool:
        return self.rc != 0

    def parsing_failed(self) -> bool:
        return bool(self.parse_error)

    @staticmethod
    def label_to_key_map() -> Dict[str, str]:
        return {
            "Entry ID": "entry_id",
            "SPIFFE ID":  "spiffe_id",
            "Parent ID": "parent_id",
            "TTL": "ttl",
            "Selector": "selector",
            "DNS name": "dns_name",
            "FederatesWith": "federates_with",
            "Downstream": "downstream",
            "Revision": "revision",
            "Admin": "admin",
            "Node": "node"
        }


def match(params: Params, identity_params: List[str], entry: RegistrationEntry) -> bool:
    # because those value may be missing because there value are the default,
    # so that they can be omitted when specifying or displaying
    def patch_with_missing_bool_identity_params(
        dict_to_patch: Dict[str, Any], identity_params: List[str]
    ) -> None:
        for p in identity_params:
            if RegistrationEntry.is_bool_entry(p) and  None == dict_to_patch.get(p):
                dict_to_patch[p] = False

    def map_list_param_to_set(params: Dict[str, Any]) -> None:
        for (key, value) in params.items():
            if RegistrationEntry.is_list_entry(key):
                if value is not None:
                    if not isinstance(value, list):
                        raise RuntimeError(f""" ValueError(f"Not a list but({type(value)}): [{key}]={value}") """)
                    params[key] = set(value)

    actual: Dict[str, Any] = {key: value for (key, value) in entry.items() if key in identity_params}
    patch_with_missing_bool_identity_params(actual, identity_params)
    expected: Dict[str,Any] = {key: value for (key, value) in params.items() if key in identity_params}
    patch_with_missing_bool_identity_params(expected, identity_params)
    map_list_param_to_set(actual)
    map_list_param_to_set(expected)
    return actual == expected


def entries_having_same_identity(
    params: Params,
    entries: List[RegistrationEntry]
) -> List[RegistrationEntry]:
    if entries is None:
        return []
    identity_params = params["identity_args"]
    # identity_params: List[str] = params.get(),
    func_having_identity_as_spefied_by_params = functools.partial(match, params, identity_params)
    filtered = list(filter(func_having_identity_as_spefied_by_params, entries))
    return filtered


def compare_ns_names(expected: Params, actual: RegistrationEntry) -> bool:

    def first_element_or_none(elements: List[str]) -> Optional[str]:
        return None if len(elements) == 0 else elements[0]

    key = "dns_name"
    ve: List[str] = expected.get_list(key)
    va: List[str] = actual.get_list(key)
    # the first elements also serve as CN in certificates.
    # They need to exactly match
    return set(ve) == set(va) \
           and first_element_or_none(ve) == first_element_or_none(va)


def compare_bool(key: str, expected: Params, actual: RegistrationEntry) -> bool:
        ve = expected.get_bool(key)
        va = actual.get_bool(key)
        return ve == va


def compare_list(key: str, expected: Params, actual: RegistrationEntry) -> bool:
        ve: List[str] = expected.get_list(key)
        va: List[str] = actual.get_list(key)
        return set(ve) == set(va)


def need_change(params: Params, actual: RegistrationEntry) -> bool:
    def setDefaultTtlIfTtlNotAvailable(params_to_patch: Dict[str, Any]) -> None:
        if params_to_patch is None:
            return
        if params_to_patch.get("ttl") is None:
            params_to_patch["ttl"] = 3600

    state = params.get("state")
    if state is None:
        raise ValueError(f"state expected but only following key are available: {params.keys()}")
    if state == 'absent':
        return bool(actual)
    elif not actual:
        return True

    expected = params
    setDefaultTtlIfTtlNotAvailable(expected)
    # ignoring entry_expiry because no present in display
    keys_to_ignore: List[str] = [
        "registration_uds_path", "state", "entry_expiry", "entry_id", "spire_server_cmd","identity_args"]
    keys_to_consider = set(filter(lambda x: not(x in keys_to_ignore), list(expected.keys())+list(actual.keys())))
    # TODO complete me
    for k in keys_to_consider:
        values_equal = False
        if k == "dns_name":
            values_equal = compare_ns_names(expected, actual)
        elif RegistrationEntry.is_list_entry(k):
            values_equal = compare_list(k, expected, actual)
        elif RegistrationEntry.is_bool_entry(k):
            values_equal = compare_bool(k, expected, actual)
        else:
            values_equal = str(expected.get(k)) == str(actual.get(k))
        if not values_equal:
            return True
    return False


class ExecServerCmdOutcome:
    def __init__(self, rc: int, stdout: str, stderr: str, cmd_args: List[str]) -> None:
        self.rc: int= rc
        self.stdout: str = stdout
        self.stderr: str = stderr
        self.cmd_args: List[str] = cmd_args

    def failed(self) -> bool:
        return self.rc != 0

    def error_message(self, action: str, extra_data: Optional[str] = None) -> str:
        if extra_data:
            return f"""Fail to execute {action}:
                    rd={self.rc}
                    stdout={self.stdout}
                    stderr={self.stderr}
                    args={self.cmd_args}"""
        else:
            return f"""Fail to execute {action}[{extra_data}]:
                    rc={self.rc}
                    stdout={self.stdout}
                    stderr={self.stderr}
                    args={self.cmd_args}"""


def exec_server_cmd(
    run_command: Callable[[Any],Tuple[int,str, str]],
    log: Callable[[str, Optional[Dict[str,str]]], None],
    sub_cmds: List[str],
    params: Dict[str, Any],
    cmd_param_keys: List[str]
) -> ExecServerCmdOutcome:
    #spiffe_id = params['spiffe_id']
    #selectors: list[string] = module.params['selector']
    #parent_id = module.params['parent_id']
    spire_server_cmd = params['spire_server_cmd']
    if not spire_server_cmd:
        raise ValueError(f"spire_server_cmd must be sprcified: {params}")
    args: List[str] = [spire_server_cmd, *sub_cmds]

    ansibleToCmdParamNames: Dict[str, str] = dict(downstream="-downstream", entry_id="-entryID",
                                  federates_with="-federatesWith", parent_id="-parentID",
                                  registration_uds_path="-registrationUDSPath",
                                  selector="-selector",spiffe_id="-spiffeID",
                                  admin="-admin", ttl="-ttl", dns_name="-dns")
    # check availabel cmd and spiffe_id
    #args: list[str] = []
    # "entry_id",
    # cmd_param_keys = [
    #     "downstream", "federates_with", "parent_id",
    #     "registration_uds_path", "selector", "spiffe_id"]
    for cmd_param_key in cmd_param_keys:
        cmd_param_value = params.get(cmd_param_key)
        if cmd_param_value != None:
            cmd_param_name = ansibleToCmdParamNames.get(cmd_param_key)
            if not cmd_param_name:
                msg = f"Unsupported cmd_param_key={cmd_param_key}; supported are {ansibleToCmdParamNames.keys()}"
                raise ValueError(msg)
            # cmd_param_type = RegistrationEntry.is_list_entry(cmd_param_key)
            if RegistrationEntry.is_list_entry(cmd_param_key):
                if not isinstance(cmd_param_value, list):
                    raise ValueError(f"Not a list but({type(cmd_param_value)}): [{cmd_param_key}]={cmd_param_value}")
                for v in cmd_param_value:
                    args.append(cmd_param_name)
                    args.append(v)
            elif RegistrationEntry.is_bool_entry(cmd_param_key):
                if not isinstance(cmd_param_value, bool):
                    raise ValueError(f"Not a boolean: [{cmd_param_key}]={cmd_param_value}")
                    # todo remove me
                if cmd_param_value:
                    args.append(cmd_param_name)
                    # not     : -downstream False
                    # but only: -downstream
            else:
                args.append(cmd_param_name)
                args.append(str(cmd_param_value))
    log(f"server cmd args::{args}", None)
    try:
        rc, stdout, stderr = run_command(args)
    except Exception as e:
        msg = f""" Error executing command:
            cmdargs: {args}
            error:{e}
            """
        raise RuntimeError(msg)

    return ExecServerCmdOutcome(rc, stdout, stderr, args)


def cmd_server_entry_show(
    run_command: Callable[[Any],Tuple[int,str, str]],
    log: Callable[[str, Optional[Dict[str,str]]], None],
    params: Params,
    ) -> SpireServerEntryShowOutcome:
    identity_args = params.get_list("identity_args")
    cmd_param_keys = [
        "registration_uds_path",
        *[e
          for e in ["downstream", "federates_with", "parent_id", "selector", "spiffe_id"]
          if e in identity_args
          ]
    ]
    exec_outcome = exec_server_cmd(run_command, log, ["entry", "show"], params, cmd_param_keys)
    if exec_outcome.failed():
        msg = exec_outcome.error_message("show entry")
        raise RuntimeError(msg)
    o = SpireServerEntryShowOutcome(exec_outcome.rc,exec_outcome.stdout,exec_outcome.stderr)
    log(f"""
        cmd_server_entry_show
            args:{exec_outcome.cmd_args}
            entries:{o}

        """, None)
    return o


def cmd_server_entry_delete(
    run_command: Callable[[Any], Tuple[int, str, str]],
    log: Callable[[str, Optional[Dict[str, str]]], None],
    params: Dict[str, Any]
) -> None:
    entry_id = params.get("entry_id")
    if not entry_id:
        msg = f"<spire-server entry update> requires entry_id(={entry_id}): args={params}"
        raise ValueError(msg)
    cmd_param_keys = [
        "registration_uds_path", "entry_id"]
    exec_outcome = exec_server_cmd(run_command, log, ["entry", "delete"], params, cmd_param_keys)
    if exec_outcome.failed():
        msg = exec_outcome.error_message("delete registration entry", entry_id)
        raise RuntimeError(msg)
    return None


def cmd_server_entry_create(
    run_command: Callable[[Any], Tuple[int, str, str]],
    log: Callable[[str, Optional[Dict[str, str]]], None],
    params: Dict[str, Any]
) -> None:
    cmd_param_keys = [
        "admin",  "dns_name",  "downstream", "entry_expiry", "federates_with",
        "node", "parent_id","registration_uds_path", "selector", "spiffe_id", "ttl"
    ]
    exec_outcome = exec_server_cmd(run_command, log, ["entry", "create"], params, cmd_param_keys)
    if exec_outcome.failed():
        msg = exec_outcome.error_message("create resgistration entry")
        raise RuntimeError(msg)
    return None


def cmd_server_entry_update(
    run_command: Callable[[Any], Tuple[int, str, str]],
    log: Callable[[str, Optional[Dict[str, str]]], None],
    params: Dict[str, Any]
) -> None:
    entry_id = params.get("entry_id")
    if not entry_id:
        msg = f"<spire-server entry update> requires entry_id(={entry_id}): args={params}"
        raise ValueError(msg)
    cmd_param_keys = ["entry_id",
        "admin",  "dns_name",  "downstream", "entry_expiry", "federates_with",
        "parent_id","registration_uds_path", "selector", "spiffe_id", "ttl"
    ]
    exec_outcome = exec_server_cmd(run_command, log, ["entry", "update"], params, cmd_param_keys)
    if exec_outcome.failed():
        msg = exec_outcome.error_message("update resgistration entry", entry_id)
        raise RuntimeError(msg)
    return None
