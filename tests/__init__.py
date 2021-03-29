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

import importlib
from importlib.abc import Loader, MetaPathFinder
import inspect
import pathlib
import sys
import types
from typing import Any


class SpireCollectionLoader(Loader):
    def module_repr(self, module):
        return repr(module)

    def load_module(self, fullname: str):
        if fullname in sys.modules:
            return sys.modules[fullname]
        if "ansible_collections.io_patricecongo.spire.plugins".startswith(fullname):
            mod = types.ModuleType(fullname)
            mod.__loader__ = self
            sys.modules[fullname] = mod
            mod.__file__ = "%s-fake-module-dir" % fullname
            # mod.__path__ = []
            mod.__setattr__("__path__", [])
            return mod

        print(f"load_module ===>{fullname}")
        module: types.ModuleType = None
        if fullname.startswith("ansible_collections.io_patricecongo.spire.plugins."):
            prefix = "ansible_collections.io_patricecongo.spire.plugins."
            actual_module_name = fullname[len(prefix):]
            module = importlib.import_module(actual_module_name)
            sys.modules[fullname] = module
        else:
            module = importlib.import_module(fullname)
            sys.modules[fullname] = module
        return module

    def get_pjt_dir(self) -> pathlib.Path:
        this_module = inspect.getmodule(self)
        pjt_dir = pathlib.Path(this_module.__file__).parent.parent
        return pjt_dir

    def get_data(self, resource_name: str) -> bytes:
        splits = resource_name.split("-fake-module-dir/", maxsplit=1)
        resource_rel_name = splits[-1]
        resource_path = self.get_pjt_dir().joinpath(resource_rel_name)
        print(
            f"get_data ==> resource_name:{resource_name}, "
            f"resource_rel_name={resource_rel_name}, "
            f"resource_path={resource_path}"
        )
        if not resource_path.exists() or resource_path.is_dir():
            return None
        data = resource_path.read_bytes()
        return data


class SpireCollectionFinder(MetaPathFinder):
    def find_module(self, fullname: str, path=None):
        if fullname.startswith("ansible_collections") or \
                fullname.startswith("ansible_collections.io_patricecongo.spire.plugins"):
            return SpireCollectionLoader()


sys.meta_path.insert(0, SpireCollectionFinder())
module_spire = importlib.import_module("ansible_collections.io_patricecongo.spire")
module_spire.__setattr__(
    "_collection_meta",
    {
        'requires_ansible': '>=2.9.10,<2.11',
    }
)

try:
    # This need to happen after setting up SpireCollectionFinder and preloading the spire-collection module.
    # Otherwise the normal collection discovery will kick-off and fail because the current execution
    # environment does not satisfy the collection structure.
    from ansible.utils.collection_loader._collection_finder import (
        _AnsibleCollectionFinder,
    )

    original_find_module = _AnsibleCollectionFinder.find_module

    def find_module(__self, fullname: str, path: Any = None):
        if fullname.startswith("ansible_collections.io_patricecongo.spire.plugins"):
            print(f"patching find_module(fullname={fullname}, path={path}) to use {SpireCollectionLoader}")
            return SpireCollectionLoader()
        return original_find_module(__self, fullname, path)

    _AnsibleCollectionFinder.find_module = find_module
except ModuleNotFoundError:
    # for ansible 2.9
    pass
