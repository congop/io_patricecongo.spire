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
import pytest
import os

def do_pytest_runtest_setup(item):
    """Run tests only when under molecule with testinfra installed."""
    try:
        import testinfra  # type: ignore
    except ImportError:
        pytest.skip("Test requires testinfra", allow_module_level=True)
    else:
        if "MOLECULE_INVENTORY_FILE" in os.environ:
            from testinfra.utils import ansible_runner
            pytest.testinfra_hosts = ansible_runner.AnsibleRunner(
                os.environ["MOLECULE_INVENTORY_FILE"]
            ).get_hosts("all")
        else:
            pytest.skip(
                "Test should run only from inside molecule.", allow_module_level=True
            )