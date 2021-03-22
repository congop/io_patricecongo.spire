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
import configparser
import io
import hashlib
import hcl # type: ignore
import json

def __blake2_hexdigest(to_digest:str) -> str:
    #h = hashlib.blake2b(salt=b"fgt565682772", person=b"file-digester", key=b"kjhiuhjhuhj")
    h = hashlib.sha256()
    to_digest_as_bytes = bytes(to_digest, "utf-8")
    h.update(to_digest_as_bytes)
    return h.hexdigest()

def digest_ini_file(init_path: str) -> str:
    config = configparser.ConfigParser()
    all_read = config.read(init_path)
    # assert size 1
    ini_normalized = io.StringIO()
    config.write(ini_normalized, space_around_delimiters=False)
    return __blake2_hexdigest(ini_normalized.getvalue())

def digest_hcl_file(hcl_path: str) -> str:
    with open(hcl_path, 'r') as fp:
      obj = hcl.load(fp)
    as_json_normalized = io.StringIO()
    json.dump(obj=obj, fp=as_json_normalized, sort_keys=True, separators=(',',':'))
    return __blake2_hexdigest(as_json_normalized.getvalue())