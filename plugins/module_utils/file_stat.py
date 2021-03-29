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
from abc import ABC, abstractmethod
import enum
import grp
import io
import os
import pwd
import stat
from typing import Any, Callable, Dict, List, NamedTuple, Set, Tuple, cast

from . import module_outcome, randoms, strings
from .diffs import DiffABC


class RemoteFileAccessFacade(ABC):
    @abstractmethod
    def remote_stat(
            self,
            task_vars: Dict[str, Any],
            file_path: str,
    ) -> Dict[str, Any]:
      pass

    @abstractmethod
    def create_remote_file(
            self,
            task_vars: Dict[str, Any],
            file_path: str,
            state: str,
            mode: str,
            module_args_overrides: Dict[str,Any] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def create_remote_tmp_dir(self) -> str:
        pass

    @abstractmethod
    def remove_remote_tmp_dir(self, path: str) -> None:
        pass

class FileModes(NamedTuple):
    """Holds chmod file mods.
    Note:
        Using 'u=xrw,g=xrw' as mode will not make chmod change permissions for
        others(o). Chmod will keep the old mode for other applying permission only
        for user(u) and group(g)
        So as a gut practice use a complete specification:  'u=xrw,g=xrw,o='
    """
    mode_dir: str
    mode_file_not_exe: str
    mode_file_exe: str

    @staticmethod
    def from_dict(
        data: Dict[str, Any], mapping: Dict[str,str]
    ) -> "FileModes":
        key_key = ["mode_dir", "mode_file_not_exe", "mode_file_exe"]
        keys = tuple(mapping.get(kk) for kk in key_key)
        if not all(keys):
            msg = f"""All mapping must be provided:
                expected keys={key_key}
                available keys={mapping.keys()}
                mapping = {keys}
            """
            raise ValueError(msg)
        modes: List[str] = [strings.trim_to_none(data.get(key)) for key in keys]
        mode_dir = modes[0]
        mode_file_not_exe = modes[1]
        mode_file_exe = modes[2]
        return FileModes(
            mode_dir=mode_dir,
            mode_file_exe=mode_file_exe,
            mode_file_not_exe=mode_file_not_exe
        )

@enum.unique
class FileType(enum.Enum):
    file="file"
    directory = "directory"
    link = "link"
    indeterminable = "indeterminable"
    block_device_file = "block_device_file"
    fifo = "fifo"
    socket = "socket"

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_stat_result_file_mode(mode:int) -> "FileType":
        if stat.S_ISREG(mode):
            return FileType.file
        elif stat.S_ISDIR(mode):
            return FileType.directory
        elif stat.S_ISLNK(mode):
            return FileType.link
        elif stat.S_ISBLK(mode):
            return FileType.block_device_file
        elif stat.S_ISFIFO(mode):
            return FileType.block_device_file
        elif stat.S_ISSOCK(mode):
            return FileType.socket

        return FileType.indeterminable

    @staticmethod
    def from_ansible_value(val: Any) -> "FileType":
        if val is None:
            return None
        return FileType(str(val))

def ansible_value_to_bool(val: Any) -> bool:
            from ansible.module_utils.parsing.convert_bool import boolean
            if any is None:
                return None
            return bool(boolean(val))

def ansible_value_to_int_octal(val: Any) -> int:
    if val is None:
        return None
    return int(val, 8)

class FileStat:
    def __init__(self,
        exists: bool,
        owner: str,
        group: str,
        mode: int,
        ftype: FileType,
        issue: str
    ) -> None:
        self.exists: bool = exists
        self.owner: str = owner
        self.group: str = group
        self.mode: int = mode
        self.ftype: FileType = ftype
        self.issue: str = issue
        if not exists and issue is None:
            msg = f"issue must be provided if file does not exists: {str(self)}"
            raise ValueError(msg)

    def mode_octal_str(self) -> str:
        if self.mode is None:
            return None
        return f"{self.mode:04o}"

    def __str__(self) -> str:
        ios = io.StringIO()
        ios.write("FileStat(")
        for key, stat in self.__dict__.items():
            ios.write(key)
            ios.write("=")
            ios.write(str(stat))
            ios.write(",")
        ios.write(")")
        return ios.getvalue()

    def get_relevant_state(
        self, relevant_attrs: List[str]
    ) -> Set[Tuple[str,Any]]:
        return {
            (relevant_attr, getattr(self, relevant_attr))
            for relevant_attr in relevant_attrs
        }

    def to_ansible_result_value(self) -> Dict[str,Any]:
        def none_enum_name_or_str(val: Any) -> str:
            if val is None:
                return None
            if isinstance(val, enum.Enum):
                return val.name
            if isinstance(val, bool):
                return str(val)
            if isinstance(val,int):
                return f"{val:04o}"
            return str(val)
        return dict({
            (k,none_enum_name_or_str(self.__dict__[k]))
            for k in ["exists", "owner", "group", "mode", "ftype", "issue"]
        })

    def copy(self) -> "FileStat":
        return FileStat(
            exists=self.exists,
            ftype=self.ftype,
            group=self.group,
            issue=self.issue,
            mode=self.mode,
            owner=self.owner
        )

    @staticmethod
    def get_attr_names_without_issue() -> List[str]:
        return ["exists", "owner", "group", "mode", "ftype"]

    @staticmethod
    def from_ansible_result_value(
        ansible_res_value: Dict[str,Any]
    ) -> "FileStat":
        fstate = FileStat(
            exists=ansible_value_to_bool(ansible_res_value["exists"]),
            ftype=FileType.from_ansible_value(ansible_res_value["ftype"]),
            group=ansible_res_value["group"],
            issue=ansible_res_value["issue"],
            mode=ansible_value_to_int_octal(ansible_res_value["mode"]),
            owner=ansible_res_value["owner"]
        )
        return fstate

    @staticmethod
    def from_issue(issue: str) -> "FileStat":
        return FileStat(
            exists=False,
            ftype=None,
            group=None,
            issue=issue,
            mode=None,
            owner=None
        )

    @staticmethod
    def from_stat_task_outcome(task_outcome: Dict[str, Any]) -> "FileStat":
        stat = task_outcome["stat"] or {}
        exists: bool = stat.get("exists")
        owner: str = None
        group: str = None
        mode: int = None
        ftype: FileType = None
        issue: str = None
        if exists :
            owner = stat.get("pw_name")
            group = stat.get("gr_name")
            mode = ansible_value_to_int_octal( stat.get("mode"))
            if stat.get("isdir"):
                ftype = FileType.directory
            elif stat.get("isreg"):
                ftype = FileType.file
            elif stat.get("islnk"):
                ftype = FileType.link
            else:
                ftype = FileType.indeterminable

        file_stat = FileStat(
            exists=exists, owner=owner, group=group,
            mode=mode, ftype=ftype, issue=issue)
        return file_stat

    @staticmethod
    def of_local_file(path:str) -> "FileStat" :

        def __get_user_name_by_uid(uid: int) -> str:
            passwdentry = pwd.getpwuid(uid)
            if passwdentry is None:
                return None
            return passwdentry.pw_name

        def __get_group_name(gid: int) -> str:
            group = grp.getgrgid(gid)
            if group is None:
                return None
            return group.gr_name
        try:
            res: os.stat_result = os.stat(path=path)
            file_stat = FileStat(
                exists=True,
                ftype=FileType.from_stat_result_file_mode(res.st_mode),
                group=__get_group_name(res.st_gid),
                issue=None,
                mode=stat.S_IMODE(res.st_mode),
                owner=__get_user_name_by_uid(res.st_uid)
            )
            return file_stat
        except FileNotFoundError as fnfe:
            return FileStat.from_issue(str(fnfe))


class FileStats:
    def __init__(
        self,
        path_to_stat: Dict[str, FileStat]
    ) -> None:
        self.__path_to_stat: Dict[str, FileStat] = path_to_stat

    def __str__(self) -> str:
        #return f"FileStats({self.__path_to_stat})"
        import io
        ios = io.StringIO()
        ios.write("FileStats(")
        for file, file_stat in self.__path_to_stat.items():
            ios.write(file)
            ios.write("=")
            ios.write(str(file_stat))
            ios.write(",")
        ios.write(")")
        return ios.getvalue()

    def get_file_stat(self, file:str) -> FileStat:
        return self.__path_to_stat.get(file)

    def files_with_stat(self) -> List[str]:
        keys = list(self.__path_to_stat.keys())
        return keys

    def exists(self, file: str) -> bool :
        fstat = self.get_file_stat(file)
        if fstat is None:
            msg = f"state not found: file={file}, available={self.files_with_stat()}"
            raise  KeyError(msg)
        return fstat.exists

    @staticmethod
    def get_local_stats(
        local_files: List[str],
    ) -> "FileStats":
        path_to_stat: Dict[str,FileStat] = {}
        for local_file in local_files:
            if local_file not in path_to_stat:
                fstat = FileStat.of_local_file(local_file)
                path_to_stat[local_file] = fstat
        return FileStats(path_to_stat)

    @staticmethod
    def get_remote_stats(
        remote_files: List[str],
        task_vars: Dict[str,Any],
        file_access: RemoteFileAccessFacade
    ) -> "FileStats":
        path_to_stat: Dict[str,FileStat] = {}
        for remote_file in remote_files:
            if remote_file not in path_to_stat:
                stat = file_access.remote_stat(
                    file_path=remote_file, task_vars=task_vars
                )
                file_stat = FileStat.from_stat_task_outcome(task_outcome=stat)
                path_to_stat[remote_file] = file_stat
        return FileStats(path_to_stat)

    def to_ansible_result_value(self) -> Dict[str,Dict[str,Any]]:
        return {
            path: fstat.to_ansible_result_value()
            for path,fstat in self.__path_to_stat.items()
        }

    @staticmethod
    def from_ansible_result(
        module_outcome: Dict[str, Any], file_stats_key:str
    ) -> "FileStats":
        ansible_file_stats = module_outcome.get(file_stats_key, None)
        if ansible_file_stats is None:
            return FileStats({})
        if not isinstance(ansible_file_stats, Dict):
            msg = f"""dict expected but found {type(ansible_file_stats)}:
                    file_stats_key = {file_stats_key}
                    ansible_file_stats = {ansible_file_stats}
                """
            raise RuntimeError(msg)
        path_to_stat: Dict[str, FileStat] = {}
        ansible_file_stats_dict = cast(Dict[str,Dict[str,Any]], ansible_file_stats)
        for path, ansible_stat in ansible_file_stats_dict.items():
            path_to_stat[path] = FileStat.from_ansible_result_value(ansible_stat)
        return FileStats(path_to_stat=path_to_stat)


class ExpectedStatsByMode:
    def __init__(
        self,
        dir_mode_to_stats: Dict[str,FileStat],
        file_mode_to_stats: Dict[str,FileStat]
    ) -> None:
        self.dir_mode_to_stats: Dict[str,FileStat] = dir_mode_to_stats
        self.file_mode_to_stats: Dict[str,FileStat] = file_mode_to_stats

    def __str__(self) -> str:
        return f"""ExpectedStatsByMode(
                dir_mode_to_stats = {self.dir_mode_to_stats},
                file_mode_to_stats = {self.file_mode_to_stats}
                )
                """

    def expected_stat_by_dir_mode(self, dir_mode: str) -> FileStat:
        return self.dir_mode_to_stats.get(dir_mode)

    def expected_stat_by_file_mode(self, file_mode: str) -> FileStat:
        return self.file_mode_to_stats.get(file_mode)

    @staticmethod
    def __to_expected_file_to_stat(
        mode_to_files: Dict[str, List[str]], mode_to_stat: Callable[[str],FileStat]
    ) -> Dict[str,FileStat]:
        file_to_stat: Dict[str,FileStat] = {}
        for mode, files in mode_to_files.items():
            file_stat = mode_to_stat(mode)
            for file in files:
                file_to_stat[file] = file_stat.copy()
        return file_to_stat

    def expected_file_stats(
        self,
        mode_to_dir: Dict[str, List[str]],
        mode_to_file: Dict[str, List[str]],
    ) -> FileStats:
        file_to_stat_dir = ExpectedStatsByMode.__to_expected_file_to_stat(
            mode_to_files=mode_to_dir, mode_to_stat=self.expected_stat_by_dir_mode
        )
        file_to_stat_file = ExpectedStatsByMode.__to_expected_file_to_stat(
            mode_to_files=mode_to_file, mode_to_stat=self.expected_stat_by_file_mode
        )
        file_stats = FileStats(path_to_stat={**file_to_stat_dir, **file_to_stat_file})
        # print(f"""calling expected_file_stats:
        #     mode_to_dir={mode_to_dir}
        #     mode_to_file={mode_to_file}
        #     file_to_stat_dir={file_to_stat_dir}
        #     file_to_stat_file={file_to_stat_file}
        #     file_stats={file_stats}
        # """)
        return file_stats

    def effective_modes(self, file_modes: FileModes) -> FileModes:
        emode_file_exe = self.file_mode_to_stats[file_modes.mode_file_exe]
        emode_file_not_exe = self.file_mode_to_stats[file_modes.mode_file_not_exe]
        emode_dir = self.dir_mode_to_stats[file_modes.mode_dir]
        return FileModes(
            mode_dir=emode_dir.mode_octal_str(),
            mode_file_exe=emode_file_exe.mode_octal_str(),
            mode_file_not_exe=emode_file_not_exe.mode_octal_str()
        )

    @staticmethod
    def assuming_present(
        dir_modes: List[str],
        file_modes: List[str],
        task_vars: Dict[str,Any],
        file_access: RemoteFileAccessFacade
        #action: SpireActionBase
    ) -> "ExpectedStatsByMode":
        def expected_file_stats_by_type(
            state: str,
            modes: List[str],
            remote_dir_base: str
        ) -> Dict[str,FileStat]:
            dir_mode_file_stats: Dict[str, FileStat] = {}
            for mode in modes:
                if mode in dir_mode_file_stats:
                    continue
                dir_name = randoms.random_file_name_with_datetime("stat-probing-dir-mode")
                dir_path = os.path.join(remote_dir_base, dir_name)
                outcome = file_access.create_remote_file(
                    task_vars=task_vars,
                    file_path=dir_path,
                    mode=mode,
                    state=state
                )
                module_outcome.assert_task_did_not_failed(
                    task_ret=outcome,
                    msg_label= f"fail create dir for mode probing [mode={mode}, dir={dir_path}]:")
                stat_outcome = file_access.remote_stat(task_vars=task_vars, file_path=dir_path)
                module_outcome.assert_task_did_not_failed(
                    task_ret=outcome,
                    msg_label= f"fail stat dir for mode probing [mode={mode}, dir={dir_path}]:")
                try:
                    file_stat = FileStat.from_stat_task_outcome(stat_outcome)
                    dir_mode_file_stats[mode] = file_stat
                except ValueError as ve:
                    msg =f"""error while FileStat.from_stat_task_outcome({dir_path})
                        error-msg = {ve}
                        outcome={outcome}
                    """
                    raise RuntimeError(msg)
            return dir_mode_file_stats

        #owner / group / octal_mode / is_dir
        remote_tmp_dir_base = file_access.create_remote_tmp_dir()
        dir_mode_file_stats: Dict[str, FileStat] = expected_file_stats_by_type(
            modes=dir_modes, remote_dir_base=remote_tmp_dir_base,state="directory"
        )

        file_mode_file_stats: Dict[str, FileStat] = expected_file_stats_by_type(
            modes=file_modes, remote_dir_base=remote_tmp_dir_base,state="touch"
        )
        file_access.remove_remote_tmp_dir(remote_tmp_dir_base)

        return ExpectedStatsByMode(dir_mode_file_stats, file_mode_file_stats)

    @staticmethod
    def assuming_absent(
        dir_modes: List[str],
        file_modes: List[str],
        task_vars: Dict[str,Any],
        file_access: RemoteFileAccessFacade
        #action: SpireActionBase
    ) -> "ExpectedStatsByMode":
        dir_mode_file_stats = {file:FileStat.from_issue("known to be absent") for file in dir_modes}
        file_mode_file_stats = {file:FileStat.from_issue("known to be absent") for file in file_modes}
        return ExpectedStatsByMode(dir_mode_file_stats, file_mode_file_stats)


class FileStatDiff(DiffABC):

    def __init__(
        self,
        file: str,
        no_diff: bool,
        diff1_2: Set[Tuple[str,Any]],
        diff2_1: Set[Tuple[str,Any]]
    ) -> None:
        #no_diff = not diff1_2 and not diff1_2
        super().__init__(no_diff=no_diff, resource_id=file)
        self.diff1_2: Set[Tuple[str,Any]] = diff1_2
        self.diff2_1: Set[Tuple[str,Any]] = diff2_1

    def __str__(self) -> str:
        return f"FileStatDiff[diff1_2={self.diff1_2}, fill2_1={self.diff2_1}]"

    def ansible_diff_header_before_after(self) -> Dict[str, str]:
        file = self.resource_id
        return {
             "after_header":  f"{file} (-={self.diff1_2})",
             "before_header": f"{file} (+={self.diff2_1})"
        }

    @staticmethod
    def diff_by_given_attrs(
        file: str,
        relevant_attrs: List[str],
        file_stat_actual:FileStat,
        file_stat_expected: FileStat
    ) -> "FileStatDiff":
        rel_attrs1 = file_stat_actual.get_relevant_state(relevant_attrs)
        rel_attrs2 = file_stat_expected.get_relevant_state(relevant_attrs)
        diff1_2 = rel_attrs1 - rel_attrs2
        diff2_1 = rel_attrs2 - rel_attrs1
        no_diff = not diff1_2 and not diff2_1
        return FileStatDiff(
            file=file, no_diff=no_diff, diff1_2=diff1_2, diff2_1=diff2_1
        )

    @staticmethod
    def diff_by_no_diff_means_not_creating(
        file: str,
        relevant_attrs: List[str],
        file_stat_actual:FileStat,
        file_stat_expected: FileStat
    ) -> "FileStatDiff":
        rel_attrs1 = file_stat_actual.get_relevant_state(relevant_attrs)
        rel_attrs2 = file_stat_expected.get_relevant_state(relevant_attrs)
        diff1_2 = rel_attrs1 - rel_attrs2
        diff2_1 = rel_attrs2 - rel_attrs1
        need_create = file_stat_expected.exists and not file_stat_actual.exists
        no_diff = not need_create
        return FileStatDiff(
            file=file, no_diff=no_diff, diff1_2=diff1_2, diff2_1=diff2_1
        )

#SystemDirDiffStrategyEnforcer
#reduce t

def get_file_statt_differ(
    system_dirs: Set[str],
    user_system_dirs: Set[str],
    file_stats_actual: FileStats,
    file_stats_expected: FileStats

) -> Callable[[str], FileStatDiff]:
    #system_dirs_pp: Set[PurePath] = {PurePath(p) for p in system_dirs}
    #user_system_dirs_pp: Set[PurePath] =  {PurePath(p) for p in user_system_dirs}

    system_dirs_pp: Set[str] = {os.path.normpath(p) for p in system_dirs}
    user_system_dirs_pp: Set[str] =  {os.path.normpath(p) for p in user_system_dirs}

    def diff_file(file: str) -> FileStatDiff:
        file = os.path.normpath(file)
        pp = os.path.normpath(file)

        if pp in system_dirs_pp:
            relevant_attrs = ["exists"]
            diff_algo = FileStatDiff.diff_by_no_diff_means_not_creating
        elif pp in user_system_dirs_pp:
            relevant_attrs = ["exists"]
            diff_algo = FileStatDiff.diff_by_no_diff_means_not_creating
        else:
            relevant_attrs = FileStat.get_attr_names_without_issue()
            diff_algo = FileStatDiff.diff_by_given_attrs
        diff = diff_algo(
            file=file, relevant_attrs=relevant_attrs,
            file_stat_actual=file_stats_actual.get_file_stat(file),
            file_stat_expected=file_stats_expected.get_file_stat(file)
        )
        return diff
    return diff_file

class FileStatsDiff:

    def __init__(
        self,
        file_stat_diffs: Dict[str,FileStatDiff]
    ) -> None:
        self.no_diff = DiffABC.no_diff_from_iterables(file_stat_diffs.values())
        self.file_stat_diffs: Dict[str,FileStatDiff] = file_stat_diffs

    @staticmethod
    def for_files(
        files: List[str],
        system_dirs: Set[str],
        user_system_dirs: Set[str],
        file_stats_actual: FileStats,
        file_stats_expected: FileStats
    ) -> "FileStatsDiff":
        differ = get_file_statt_differ(
            file_stats_actual=file_stats_actual,
            file_stats_expected=file_stats_expected,
            system_dirs=system_dirs,
            user_system_dirs=user_system_dirs
        )
        file_stat_diffs: Dict[str,FileStatDiff] = {
            file : differ(file)
            for file in files
        }
        return FileStatsDiff(file_stat_diffs=file_stat_diffs)

    def __str__(self) -> str:
        import io
        ios = io.StringIO("FileStatsDiff(")
        ios.write("no_diff=")
        ios.write(str(self.no_diff))
        ios.write(",\n")
        ios.write("file_statt_dif={")
        files_with_no_diff: List[str] = []
        for file, file_stat_diff in self.file_stat_diffs.items():
            if file_stat_diff.no_diff:
                files_with_no_diff.append(file)
            else:
                ios.write(file)
                ios.write("=")
                ios.write(str(file_stat_diff))
                ios.write(",")
        ios.write("files_with_no_diff=")
        ios.write(str(files_with_no_diff))
        ios.write("}")
        ios.write(")")
        return ios.getvalue()
