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
import pathlib
from typing import List, Optional, Tuple, cast

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import Certificate


def get_cert_san(certpath: str) -> Tuple[Optional[str], Optional[int],Optional[str]]:

    if not os.path.exists(certpath):
        return None, 0, f"der certificate path [{certpath}] does not exists"

    certpath_obj: pathlib.Path = pathlib.Path(certpath)
    cert_file_content = certpath_obj.read_bytes()
    # cert = x509.load_pem_x509_certificate(cert_file_content, default_backend())
    cert: Certificate = x509.load_der_x509_certificate(cert_file_content, default_backend())
    # san1=mycert.extensions.get_extension_for_oid(x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    extension_san: x509.Extension = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    if not extension_san:
        return None, 0, "x509.SubjectAlternativeName not available in certificate"
    san: x509.SubjectAlternativeName = cast(x509.SubjectAlternativeName, extension_san.value)
    san_value: List[str] = san.get_values_for_type(x509.GeneralName)
    if not san_value:
        return None, 0, "Value of type[x509.GeneralName] not available in x509.SubjectAlternativeName"
    return san_value[0], cert.serial_number, None
