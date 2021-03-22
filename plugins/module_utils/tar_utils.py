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
def extract_tar_member(tar_gz_archive_path: str, tar_member_name_suffix: str) -> str:
    """extracts tar(gz) archive member.
    Parameters:
        tar_gz_archive_path: the path if the downloaded achive
        tar_member_name_suffix: a suffix used to select the member to extract.
                                e.g. /bin/spire-agent to extract spire-agent library
    """
    import os
    import tarfile
    with tarfile.open(tar_gz_archive_path) as tar:
        spire_agent_binary_as_list = [
            e for e in tar
            if str(e.name).endswith(tar_member_name_suffix) and e.name.startswith("./")]
        if 1 != len(spire_agent_binary_as_list):
            tar_gz_ls = [e.name for e in tar]
            msg = f"""could not find {tar_member_name_suffix} member in tar.gz
                    tar-gz: {tar_gz_archive_path}
                    tar-gz-content: {tar_gz_ls}
                """
            raise RuntimeError(msg)
        target_dir = os.path.dirname(tar_gz_archive_path)
        tar.extractall(members=spire_agent_binary_as_list, path=target_dir)
        target_file = os.path.join(target_dir, spire_agent_binary_as_list[0].name)
        target_file = os.path.normpath(target_file)

    return target_file
