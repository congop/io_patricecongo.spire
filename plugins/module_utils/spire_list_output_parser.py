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
from typing import Dict, List, Union


def parse_list_stdout(to_parse: str, list_value_labels: List[str] = None) -> List[Dict[str, Union[str, List[str]]]]:
    def contibute_to_entry(
                            entry: Dict[str, Union[str, List[str]]],
                            label: str, value: str
    ) -> None:
        is_list_entry = list_value_labels and (label in list_value_labels)
        if is_list_entry:
            list_value = entry.get(label)
            if list_value is None:
                list_value = []
                entry[label] = list_value
            elif not isinstance(list_value, list):
                msg = f"Bad type for list item: label:{label}, type-label:{type(list_value)}, value={value}"
                raise RuntimeError(msg)
            list_value.append(value)
        else:
            old_value = entry.get(label)        
            if old_value is not None:
                msg = f"""Non list value cannot have more than one element: 
                            label={label} old_value={old_value}, value={value}
                        """
                raise RuntimeError(msg)
            entry[label] = value

    if not to_parse:
        return []

    entries: List[Dict[str,Union[str, List[str]]]]=[]
    line_nr = 0
    nr_of_entries = 0
    detected = False
    entry: Dict[str, Union[str, List[str]]] = None
    for line in to_parse.splitlines():
        line_nr = line_nr + 1
        if not detected:
            # expected format: 
            #   Found 23 entries
            #   Found 5 attested agents:
            splits = line.split(" ")
            if 3 > len(splits):
                continue
            if not ("Found" == splits[0]):
                continue
            try:
                nr_of_entries = int(splits[1])
                detected = True
                # in case we do not have a new line between Found line and first entry
                entry = {}
                entries.append(entry)
            except Exception as e:
                e_str = str(e)
                raise ValueError(f"Bad found-entries line: error ==> {e_str} Line {line_nr} ==> {line}")
        else:
            if (not line) or line.isspace():
                if entries and not entries[-1]:
                    # multiple empty line separator between elements
                    continue
                entry = {}
                entries.append(entry)
            else: 
                splits = line.split(":", 1)
                if 2 != len(splits):
                    raise ValueError(f"Bad line formal: Line Nr. {line_nr} --> {line}")
                label = splits[0].strip()
                value = splits[1].strip()
                # entry[key] = value
                contibute_to_entry(entry, label, value)
                # parse the entry
                # format:
                # Entry ID      : 0ccd30fb-2e30-40a7-918c-a282b16ee9e0
                # SPIFFE ID     : spiffe://example.org/myagent1/k8s
                # Parent ID     : spiffe://example.org/myagent1
                # TTL           : 3600
                # Selector      : unix:gid:1000,unix:user:etcd
                # DNS name      : api.sapone.k8s
                # DNS name      : kubernetes
                pass
    if entries and not entries[-1]:
        entries.pop()
    return entries
