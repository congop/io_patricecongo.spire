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


class ServerTemplates:

    def __init__(self) -> None:
        super().__init__()
        module_file = __file__
        tmpl_dir = os.path.dirname(os.path.realpath(module_file))
        self.tmpl_service = os.path.join(tmpl_dir, "spire-server-default.service.j2")
        self.tmpl_service_env = os.path.join(tmpl_dir, "spire-server-default.service-env.j2")
        self.tmpl_conf = os.path.join(tmpl_dir, "spire-server-default.conf.j2")
