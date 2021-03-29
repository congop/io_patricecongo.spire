from abc import ABC, abstractmethod
import os
from typing import Dict, List, Tuple
from .file_stat import FileModes


class SpireCmptDirs(ABC):

    def __init__(self,
        config_dir: str,
        data_dir: str,
        install_dir: str,
        service_dir: str,
        log_dir: str,
        service_name: str,
        exec_file_name: str,
        conf_file_name: str,
        env_file_name: str
    ) :
        self.config_dir: str = os.path.normpath(config_dir)
        self.data_dir: str = os.path.normpath(data_dir)
        self.install_dir: str = os.path.normpath(install_dir)
        self.install_dir_bin: str = None
        if install_dir:
            self.install_dir_bin = os.path.join(self.install_dir, "bin")
        self.service_dir: str = os.path.normpath(service_dir)
        self.log_dir: str = os.path.normpath(log_dir)
        self.service_name = service_name
        self.service_full_name = service_name
        if service_name:
            if service_name.endswith(".service"):
                self.service_name = os.path.splitext(service_name)[0]
            else:
                self.service_full_name = f"{service_name}.service"
        self.path_conf_file: str = os.path.join(self.config_dir, conf_file_name)
        self.path_env_file: str = os.path.join(self.config_dir, env_file_name)
        self.path_service_file: str = os.path.join(self.service_dir, self.service_full_name)
        self.path_executable: str = os.path.join(self.install_dir_bin, exec_file_name)

    def __str__(self) -> str:

        return f"{self.__class__.__name__}({self.__dir__})"


    def expected_dirs(self) -> List[str]:
        return [
            self.config_dir,
            self.data_dir,
            self.install_dir,
            self.install_dir_bin,
            self.service_dir,
            self.log_dir,
        ]

    def expected_files_not_exec(self) -> List[str]:
        return [
            self.path_conf_file,
            self.path_env_file,
            self.path_service_file,
            *self.extra_expected_files_not_exec()
        ]

    @abstractmethod
    def extra_expected_files_not_exec(self) -> List[str]:
        pass

    def expected_files_exec(self) -> List[str]:
        return [
            self.path_executable,
        ]

    def expected_dirs_and_files(self) -> List[str]:
        return [
            *self.expected_dirs(),
            *self.expected_files_not_exec(),
            *self.expected_files_exec()
        ]

    def mode_to_expected_dirs(
        self, file_modes: FileModes
    ) -> Dict[str,List[str]]:
        return {file_modes.mode_dir: self.expected_dirs()}

    def mode_to_expected_files(
        self, file_modes: FileModes
    ) -> Dict[str,List[str]]:
        mode_to_file_mapping: List[Tuple[str,List[str]]] = [
                (file_modes.mode_file_not_exe, self.expected_files_not_exec()),
                (file_modes.mode_file_exe, self.expected_files_exec()),
        ]
        mtf: Dict[str,List[str]] = {}
        for mode, files in mode_to_file_mapping:
            tfiles = mtf.get(mode)
            if tfiles is None:
                tfiles = []
                mtf[mode] = tfiles
            tfiles.extend(files)
        return mtf