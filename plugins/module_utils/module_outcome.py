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

from typing import Any, Dict

def failed(task_ret: Dict[str, Any]) -> bool:
  if task_ret.get("failed"):
    return True
  return False

def std_out_err(task_ret: Dict[str, Any]) -> str:
  stdout = task_ret.get("stdout")
  stderr = task_ret.get("stderr")
  return f"stderr:{stdout} \n stderr={stderr}"

def assert_shell_or_cmd_task_successful(
        task_ret: Dict[str, Any],
        msg_label: str) -> None:
    if task_ret.get("rc") != 0:
        msg = f"""
            {msg_label}:
            {task_ret}
            """
        raise RuntimeError(msg)
    return

def assert_task_did_not_failed(
        task_ret: Dict[str, Any],
        msg_label: str
) -> None:
    if task_ret.get("failed"):
        msg = f"""
            {msg_label}:
            {task_ret}
            """
        raise RuntimeError(msg)
    return