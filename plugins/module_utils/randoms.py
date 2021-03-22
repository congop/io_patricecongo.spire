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
import random
from . import strings

def __make_random() -> random.Random:
    ran = random.Random()
    return ran

__random: random.Random = __make_random()

def next_uint32() -> int:
    return __random.randint(0,2**32)

def random_file_name_with_datetime(name_prefix: str, name_suffix: str=None) -> str:
    # '2021-02-24-10_42_28'
    datetime_now_str = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M_%S")
    prefix_format_part = ""
    prefix_sep = ""
    if not strings.is_blank(name_prefix):
        prefix_format_part = name_prefix.strip()
        prefix_sep = "-"
    suffix_format_part, suffix_sep = ("","")
    if not strings.is_blank(name_suffix):
        suffix_format_part = name_prefix.strip()
        suffix_sep = "-"
    ran_value = next_uint32()
    #padding ran_value to 9 characters so that 0 and 2**32 will get the same size
    fname = f"{prefix_format_part}{prefix_sep}{ran_value:09x}{suffix_sep}{suffix_format_part}"
    return fname
    # '93d7a4a9'