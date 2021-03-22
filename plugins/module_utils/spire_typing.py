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
import enum
from re import S
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Type, TypeVar, Union

from .diffs import DiffABC

TStateEnum = TypeVar('TStateEnum', bound='StateEnum')


@enum.unique
class StateEnum(enum.Enum):
    @classmethod
    def by_name(cls: Type[TStateEnum], name: str) -> Optional[TStateEnum]:
        return cls.__members__.get(name, None)

    @classmethod
    def names(cls: Type[TStateEnum]) -> List[str]:
        return [*cls.__members__]

    @classmethod
    def values(cls: Type[TStateEnum]) -> List[TStateEnum]:
        return [*cls.__members__.values()]

@enum.unique
class State(StateEnum):
    present = "present"
    absent = "absent"

    @staticmethod
    def from_info(spire_component_installed: bool) -> "State":
        if spire_component_installed:
            return State.present
        else:
            return State.absent

@enum.unique
class SubStateServiceInstallation(StateEnum):
    not_installed = "not_installed"
    installed = "installed"
    enabled = "enabled"

    @staticmethod
    def from_info(
        is_service_enabled: bool, is_service_installed: bool
    ) -> "SubStateServiceInstallation":
        if is_service_enabled:
            return SubStateServiceInstallation.enabled
        elif is_service_installed:
            return SubStateServiceInstallation.installed
        else:
            return SubStateServiceInstallation.not_installed


@enum.unique
class SubStateAgentRegistered(StateEnum):
    yes = "yes"
    no = "no"
    partially = "partially"
    indeterminable = "indeterminable"

    @staticmethod
    def from_bool_or_str(input_value: Union[bool, str, None]) -> "SubStateAgentRegistered":
        if input_value is True:
            return SubStateAgentRegistered.yes
        elif input_value is False or input_value is None:
            return SubStateAgentRegistered.no
        elif isinstance(input_value, str):
            result = SubStateAgentRegistered.by_name(input_value)
            if result is None:
                raise ValueError(
                    f"not a value str input value: input_value={input_value}, "
                    f"valid-values={SubStateAgentRegistered.names()}")
            return result
        else:
            raise ValueError(
                f"input_value must be a bool or a str but is: type=type({type(input_value)}, value={input_value})")


@enum.unique
class SubStateServiceStatus(StateEnum):
    stopped = "stopped"
    started = "started"
    healthy = "healthy"

    def __contains__(self, candidate: "SubStateServiceStatus") -> bool:
        if self == SubStateServiceStatus.healthy:
            return self == candidate or SubStateServiceStatus.started == candidate
        return self == candidate

    @staticmethod
    def from_info(
        is_healthy: bool, is_service_running: bool
    ) -> "SubStateServiceStatus":
        if is_healthy:
            return SubStateServiceStatus.healthy
        elif is_service_running:
            return SubStateServiceStatus.started
        else:
            return SubStateServiceStatus.stopped


class StateOfAgent:
    def __init__(
            self,
            state: State,
            substate_service_installation: Optional[SubStateServiceInstallation],
            substate_service_status: Optional[SubStateServiceStatus],
            substate_agent_registered: Optional[SubStateAgentRegistered]
    ) -> None:
        if state is None or \
                (state is State.present \
                 and (substate_service_installation is None
                      or substate_service_status is None
                      or substate_agent_registered is None)):
            msg = f"""state must be non None
                and when {State.present} service installation, status and registered must be given
                state={state}
                substate_service_installation={substate_service_installation}
                substate_service_status={substate_service_status}
                substate_agent_registered={substate_agent_registered}
                """
            raise ValueError(msg)
        self.state: State = state
        self.substate_service_installation: SubStateServiceInstallation = substate_service_installation
        self.substate_service_status: SubStateServiceStatus = substate_service_status
        self.substate_agent_registered: SubStateAgentRegistered = substate_agent_registered

    def need_change(
        self,
        expected: "StateOfAgent",
        ignore_substate_agent_registered: bool = False
    ) -> bool:
        if self.state == State.absent:
            return bool(State.absent != expected.state)
        matches_expectations =  bool(
            State.present == expected.state
            and self.substate_service_installation == expected.substate_service_installation
            and self.substate_service_status in expected.substate_service_status
            and (
                    ignore_substate_agent_registered
                    or self.substate_agent_registered == expected.substate_agent_registered
                )
        )
        return not matches_expectations

    def need_srv_installation_change(
        self,
        expected: "StateOfAgent"
    ) -> bool:
        return self.substate_service_installation != expected.substate_service_installation

    def substate_agent_registered_name(self) -> str:
        if self.substate_agent_registered is None:
            return None
        return self.substate_agent_registered.name

    def substate_service_installation_name(self) -> str:
        if self.substate_service_installation is None:
            return None
        return self.substate_service_installation.name

    def substate_service_status_name(self) -> str:
        if self.substate_service_status is None:
            return None
        return self.substate_service_status.name

    def to_ansible_return_data(self) -> Dict[str, str]:
        data = {"actual_state": self.state.name}
        if self.substate_agent_registered:
            data["actual_substate_agent_registered"] = self.substate_agent_registered_name()
        if self.substate_service_installation:
            data["actual_substate_service_installation"] = self.substate_service_installation_name()
        if self.substate_service_status:
            data["actual_substate_service_status"] = self.substate_service_status_name()
        return data

    @staticmethod
    def from_task_args(task_args: Dict[str, Any]) -> "StateOfAgent":
        args_state = task_args.get("state")
        args_installation = task_args.get("substate_service_installation")
        args_status = task_args.get("substate_service_status")
        args_registered = task_args.get("substate_agent_registered")
        if isinstance(args_registered, str):
            # just being lenient
            args_registered = args_registered.lower()

        return StateOfAgent(
            state=State.by_name(args_state),
            substate_agent_registered=SubStateAgentRegistered.from_bool_or_str(args_registered),
            substate_service_installation=SubStateServiceInstallation.by_name(args_installation),
            substate_service_status=SubStateServiceStatus.by_name(args_status)
        )


class BoolResultWithIssue(NamedTuple):
    res: bool
    issue: str

    def to_tuple(self) -> Tuple[Optional[bool], Optional[str]]:
        return self.res, self.issue


class CmdExecOutcome(NamedTuple):
    rc: int
    stdout: str
    stderr: str

    def succeeded(self) -> bool:
        return 0 == self.rc

    def failed(self) -> bool:
        return 0 != self.rc

    def has_blank_stdout(self) -> bool:
        return not self.stdout or self.stdout.isspace()

    def has_blank_stderr(self) -> bool:
        return not self.stderr or self.stderr.isspace()

    def has_blank_stdout_and_stderr(self) -> bool:
        return self.has_blank_stdout() and self.has_blank_stderr()

CmdExecCallable = Callable[[Any], CmdExecOutcome]

# TODO  make version part of this object
class StateOfServer:
    def __init__(
            self,
            state: State,
            substate_service_installation: Optional[SubStateServiceInstallation],
            substate_service_status: Optional[SubStateServiceStatus],
    ) -> None:
        if state is None or \
                (state is State.present \
                 and (substate_service_installation is None
                      or substate_service_status is None)):
            msg = f"""state must be non None
                and when {State.present} service installation, status and registered must be given
                state={state}
                substate_service_installation={substate_service_installation}
                substate_service_status={substate_service_status}
                """
            raise ValueError(msg)
        self.state: State = state
        self.substate_service_installation: SubStateServiceInstallation = substate_service_installation
        self.substate_service_status: SubStateServiceStatus = substate_service_status

    def __str__(self) -> str:
        return f"StateOfServer({self.state},{self.substate_service_installation}, {self.substate_service_status})"

    def need_change(
        self,
        expected: "StateOfServer"
    ) -> bool:
        if self.state == State.absent:
            return bool(State.absent != expected.state)
        matches_expectations =  bool(
            State.present == expected.state
            and self.substate_service_installation == expected.substate_service_installation
            and self.substate_service_status in expected.substate_service_status
        )
        return not matches_expectations

    def need_srv_installation_change(
        self,
        expected: "StateOfServer"
    ) -> bool:
        return self.substate_service_installation != expected.substate_service_installation \
                or self.substate_service_status != expected.substate_service_status

    def substate_service_installation_name(self) -> str:
        if self.substate_service_installation is None:
            return None
        return self.substate_service_installation.name

    def substate_service_status_name(self) -> str:
        if self.substate_service_status is None:
            return None
        return self.substate_service_status.name

    def to_ansible_return_data(self) -> Dict[str, str]:
        data = {"actual_state": self.state.name}
        if self.substate_service_installation:
            data["actual_substate_service_installation"] = self.substate_service_installation_name()
        if self.substate_service_status:
            data["actual_substate_service_status"] = self.substate_service_status_name()
        return data

    @staticmethod
    def from_ansible_return_data(task_outcome: Dict[str, Any]) -> "StateOfServer":
        state_str = task_outcome["actual_state"]
        substate_srv_installation_str = task_outcome["actual_substate_service_installation"]
        substate_srv_status_str = task_outcome["actual_substate_service_status"]
        substate_srv_installation = SubStateServiceInstallation.by_name(substate_srv_installation_str)
        substate_srv_status = SubStateServiceStatus.by_name(substate_srv_status_str)
        sos = StateOfServer(
                    state=State.by_name(state_str),
                    substate_service_installation=substate_srv_installation,
                    substate_service_status=substate_srv_status
                )
        return sos



    @staticmethod
    def from_task_args(task_args: Dict[str, Any]) -> "StateOfServer":
        args_state = task_args.get("state")
        args_installation = task_args.get("substate_service_installation")
        args_status = task_args.get("substate_service_status")
        return StateOfServer(
            state=State.by_name(args_state),
            substate_service_installation=SubStateServiceInstallation.by_name(args_installation),
            substate_service_status=SubStateServiceStatus.by_name(args_status)
        )

    def ansible_diff_header_str(self, resource: str) -> str:
        state = self.state.name
        sstate_srv_inst = self.substate_service_installation_name()
        sstate_srv_status = self.substate_service_status_name()
        header_str = f"{resource} ({state} // {sstate_srv_inst} // {sstate_srv_status})"
        return header_str

class StateOfServerDiff(DiffABC):

    def __init__(
        self, actual: StateOfServer, expected: StateOfServer
    ) -> None:
        no_diff: bool = not actual.need_change(expected=expected)
        super().__init__(no_diff=no_diff, resource_id="state-of-spire-server")
        self.actual: StateOfServer = actual
        self.expected: StateOfServer = expected

    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        return {
             "after_header": self.actual.ansible_diff_header_str(self.resource_id),
             "before_header": self.expected.ansible_diff_header_str(self.resource_id)
        }