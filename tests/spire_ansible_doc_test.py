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
from typing import Any, Callable, Dict, Tuple
from yamllint import linter
import yaml
import pytest
from yamllint.config import YamlLintConfig
from ansible_collections.io_patricecongo.spire.plugins.modules import(
    spire_agent,
    spire_agent_registration_info,
    spire_server,
    spire_agent_info,
    spire_server_info,
    spire_spiffe_id,
)

from ansible.parsing import(
    plugin_docs,
)
from types import (
    FunctionType, ModuleType,
)

from importlib import import_module

def get_module_args(mod: ModuleType) -> Dict[str, Dict[str,Any]]:
    _module_args_func: Callable[[], Dict[str, Dict[str,Any]]]  = getattr(mod,"_module_args")
    if not isinstance(_module_args_func, FunctionType ):
        msg = f"module does not have a _module_args function, but {dir(mod)}"
        raise ValueError(msg)
    return _module_args_func()

def check_attr_yaml(mod: ModuleType, attr_name: str) -> Tuple[bool, str]:
    result: str  = getattr(mod,attr_name)
    if not isinstance(result, str ):
        msg = f"{attr_name} expected to be a str but was {type(result)}"
        return False, msg
    conf ="""
    extends: default
    rules:
        line-length: disable
        empty-lines: disable
        truthy: disable
        document-start: disable
        empty-values: enable
        quoted-strings:
            required: false
            extra-required: ['^.*:\s']
    """
    problems = list(linter.run( input=result, conf=YamlLintConfig(conf)))
    if problems:
        return False, str(problems)
    return True, None

@pytest.mark.parametrize(
    "module",
    [
        (spire_agent),
        (spire_agent_info),
        (spire_agent_registration_info),
        (spire_server),
        (spire_server_info),
        (spire_spiffe_id)
    ]
)
def test_spire_module_doc_okay(module: ModuleType) -> None:
    module_file = module.__file__
    # {'doc':xxx, 'plainexamples':xxx, 'returndocs':xxx, 'metadata':xxx, 'seealso':xxx]
    docs: Dict[str, Any] = plugin_docs.read_docstring(filename=module_file, ignore_errors=False)
    #{[}'module':xxxx, 'short_description':xxxx, 'version_added':xxx, 'description':xxx, 'options':xxxx, 'author':xxx}
    doc: Dict[str, Dict[str,Any]] = docs["doc"]
    options: Dict[str,Any] = doc["options"]
    option_keys = set(options.keys())
    module_args = get_module_args(module)
    args_keys = set(module_args.keys())
    doc_ok, doc_issues = check_attr_yaml(mod=module, attr_name="DOCUMENTATION")
    ret_ok, ret_issues = check_attr_yaml(mod=module, attr_name="RETURN")

    if not (option_keys == args_keys and ret_ok and doc_ok):
        msg= f"""Entries in DOCUMENTATION do not match those in module_args:
            to remove:{option_keys-args_keys}
            to add   :{args_keys-option_keys}
            option_keys     : {option_keys}
            module_args_keys: {args_keys}
            return_yaml_issue: {ret_issues}
            documentation_yaml_issue: {doc_issues}
        """
        pytest.fail(msg=msg, pytrace=False)
