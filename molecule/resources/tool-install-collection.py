#!python3
# -*- coding: utf-8 -*-
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

import os
import subprocess
import sys
from typing import Tuple
import yaml


def get_env_var(key: str) -> str:
      pjt_dir = os.environ.get(key)
      if not pjt_dir:
            raise RuntimeError(
                  f"""Could not find env variable(key={key}
                  ENV={os.environ}
                  """
            )
      return pjt_dir

def get_project_directory() -> str:
      key = "MOLECULE_PROJECT_DIRECTORY"
      pjt_dir = os.environ.get(key)
      if not pjt_dir:
            raise RuntimeError(
                  f"""Could not find project directory(key={key}
                  ENV={os.environ}
                  """
            )
      return pjt_dir

def get_ansible_collection_paths() -> str:
      return os.getenv("ANSIBLE_COLLECTIONS_PATHS")

def modelcule_debug() -> bool:
      md = os.getenv("MOLECULE_DEBUG", "False")
      return md != None and md.lower() in ["true", "yes"]


def get_collection_info() -> Tuple[str,str,str]:
      pjt_dir = get_project_directory()
      galaxy_yml = os.path.join(pjt_dir, "galaxy.yml")
      if not os.path.exists(galaxy_yml):
            raise FileNotFoundError(
                  f"galaxy yml file does not exists:{galaxy_yml}"
                  )
      with open(galaxy_yml) as stream:
            try:
                  galaxy_xml_obj = yaml.safe_load(stream)
                  c_name = galaxy_xml_obj.get("name")
                  c_ns = galaxy_xml_obj.get("namespace")
                  c_version = galaxy_xml_obj.get("version")
                  if not c_name or not c_ns or not c_version:
                        msg = f"""Collection name, namespace and version must be specified in galaxy.yml
                              galaxy-yml-file={galaxy_yml}
                              namespace={c_ns}, name={c_name}, version={c_version}
                              parse yaml obj_type= {type(galaxy_xml_obj)}
                              parse yaml obj= {galaxy_xml_obj}
                        """
                        raise RuntimeError(msg)
                  return c_ns, c_name, c_version
            except yaml.YAMLError as exc:
                  msg = f"""failed to parse galaxy-yml
                              galaxy-yml-file={galaxy_yml}
                              error= {exc}
                        """
                  raise RuntimeError(msg)

def anible_galaxy_install_to_collections_path(collections_path: str, tar_gz_distribution):
      if not os.path.exists(tar_gz_distribution):
            raise FileNotFoundError(f"tar_gz_distribution({tar_gz_distribution} does not exists")
      args = ["ansible-galaxy", "collection", "install", tar_gz_distribution, "-p", collections_path, "-vvv", "--force"]
      # to avoid warning that this installation will not be picked up by ansible
      env_galaxy = { **os.environ, "ANSIBLE_COLLECTIONS_PATHS": collections_path}
      p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_galaxy)
      if p.returncode != 0:
            p_galaxy_version =  subprocess.run(["ansible-galaxy", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_galaxy)
            msg = f"""ansible-galaxy call failed:
                        ret= {p}
                        p_galaxy_version= {p_galaxy_version}
                  """
            raise RuntimeError(msg)
      if modelcule_debug():
            print(f"""Ansible-Galaxy collection install succeeded: {args}
                  stdout: {str(p.stdout)}
                  stderr: {str(p.stderr)}
                  """
            )

def get_ansible_collections_path() -> str:
      # we know this should be one of the collections paths
      ephemeral_dir = get_env_var("MOLECULE_EPHEMERAL_DIRECTORY")
      collections_path = os.path.join(ephemeral_dir, "collections")
      collections_paths = get_ansible_collection_paths()
      if collections_paths:
            cpaths = collections_paths.split(os.pathsep)
            c_abspaths = list( map(lambda p: os.path.abspath(p), cpaths))
            collections_path_abs = os.path.abspath(collections_path)
            if not collections_path in collections_path_abs:
                  msg = f"""Built collections_path not in environment ANSIBLE_COLLECTIONS_PATH.
                        This may result in ansible not picking up the collections installed using this location.
                              collections_path              ={collections_path}
                              collections_path_abs          ={collections_path_abs}
                              ansible_collections_paths     ={cpaths}
                              ansible_collections_paths_abs ={cpaths}
                        """
                  print(msg, file= sys.stderr)
      return collections_path

def main() -> None :
      try:
            c_info: Tuple[str,str,str] = get_collection_info()
            dist_tar_gz_name = c_info[0] + "-" + c_info[1] + "-" + c_info[2] + ".tar.gz"
            dist_tar_gz_path = os.path.join(get_project_directory(), dist_tar_gz_name)

            a_collections_path = get_ansible_collections_path()
            if not os.path.exists(a_collections_path):
                  os.makedirs(a_collections_path)

            anible_galaxy_install_to_collections_path(a_collections_path, dist_tar_gz_path)
      except Exception as exc:
            print(str(exc), file=sys.stderr)
            exit(1)


if __name__ == '__main__':
      main()
