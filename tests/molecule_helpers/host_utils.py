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
from typing import Any, Dict, Iterable, List, Optional

from ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_typing import (
    CmdExecOutcome,
)
from testinfra.backend.base import CommandResult
from testinfra.host import Host

def assert_successful(res: CommandResult, action:str ) -> None:
    if res.failed:
            raise RuntimeError(f""" failed  to: {action}
                    result: {res}
                    """)

class HostFuncsAdapter:

    def __init__(
        self,
        host: Host,
        user_name: str = None
    ):
        self.host: Host = host
        self.user_name: str = user_name
        self.change_user_cmd_parts = self.__change_user_cmd(user_name)

    def __get_current_user(self) -> str:
        res: CommandResult = self.host.run("whoami")
        assert_successful(res, "whoami")
        return str(res.stdout).strip()

    def __change_user_cmd(self, user_name:str) -> List[str]:
        if user_name is not None:
            user_name = user_name.strip()
        if not user_name:
            return []
        current_user = self.__get_current_user()
        if current_user == user_name:
            return []

        return ["sudo","-u", user_name]


    def run_command(self, cmd_parts:Any) -> CmdExecOutcome:
        if not isinstance(cmd_parts,Iterable):
            raise ValueError(
                f"""cmd_parts must be an Iterable:
                type:{type(cmd_parts)},
                value={cmd_parts} """
            )
        args = [*self.change_user_cmd_parts, *cmd_parts]
        cmd_str = " ".join(args)
        res: CommandResult = self.host.run(cmd_str)
        print(res)
        return CmdExecOutcome(res.rc, res.stdout, res.stderr)

    def run_command_with_ansible(self, cmd_parts:Any) -> CmdExecOutcome:
        """
        use ansible itself to run the given command.
        This supports running the command as another user using <su>.
        Why the choice of <su> :
            - making <system --user ... > run correctly.
              which means without<. "Failed to connect to bus: No such file or directory"
            - to work <system --user --> require:
                - a <systemd --user>-process running under th user
                - d-bus available
                - environment containing: XDG_RUNTIME_DIR=/run/user/$(id -u $otherUser)
            - <su> does provide it (in contrary to <sudo -u>)
                may be because some log-in process is done by <su>
        """
        if not isinstance(cmd_parts,Iterable):
            raise ValueError(
                f"""cmd_parts must be an Iterable:
                type:{type(cmd_parts)},
                value={cmd_parts} """
            )
        args = [*cmd_parts]
        cmd_str = " ".join(args)
        if self.change_user_cmd_parts:
            cmd_ret = self.host.ansible(
                "command",
                cmd_str,
                check=False,
                become=True,
                become_user=self.user_name,
                become_method="su"
                )
        else:
            cmd_ret = self.host.ansible(
                "command",
                cmd_str,
                check=False,
                )
        stdout = cmd_ret["stdout"]
        stderr = cmd_ret["stderr"]
        rc = cmd_ret["rc"]
        return CmdExecOutcome(rc, stdout, stderr)

    def no_log(self, mesg:str, msg_args:Optional[Dict[str,str]]) -> None:
        pass

    def file_exists(self, path:str) -> bool:
        if not path:
            return False
        #res: CommandResult = self.host.run("ls %s", path)
        res: CmdExecOutcome = self.run_command(["ls", path])
        return bool(res.succeeded())

    def docker_copy_agent_svid_der(self, agent_data_dir_local) -> None:
        import subprocess
        cp_cmd_args = [
            "docker", "cp",
            "spire_agent:/var/lib/spire-agent/data/agent/agent_svid.der",
            agent_data_dir_local
        ]
        completed_proc: subprocess.CompletedProcess = subprocess.run(
                                                            cp_cmd_args,
                                                            stderr=subprocess.PIPE,
                                                            stdout=subprocess.PIPE)
        if not completed_proc.returncode != 0:
            print(completed_proc)

    def __repr__(self):
        return f"{type(self).__name__}(host={self.host}, change_user_cmd_parts={self.change_user_cmd_parts})"
