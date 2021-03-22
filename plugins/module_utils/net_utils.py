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
from ansible.inventory.host import Host
import os
from urllib.parse import urlparse
from typing import cast

def url_filename(url: str) -> str:
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    return filename


def is_localhost(host: Host) -> bool:
    addr: str = host.address
    if "localhost" == addr or "127.0.0.1" == addr or "::1" == addr:
        return True
    try:
        import ipaddress
        ipaddr = ipaddress.ip_address(addr)
        return cast(bool, ipaddr.is_loopback)
    except ValueError:
        # this is just not an ip address
        pass
    return False