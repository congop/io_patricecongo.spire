##
## Copyright (c) 2021 Patrice Congo <@congop>.
##
## This file is part of io_patricecongo.spire
## (see https://github.com/congop/io_patricecongo.spire).
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program. If not, see <http://www.gnu.org/licenses/>.##

# This is a Jinja2 file, not using .j2 suffix to have docker highlighting and autocompletion
#   - using absolute path when copying because the molecule provisioner will create the final
#     Dockerfile in ${MOLECULE_EPHEMERAL_DIRECTORY}/Dockerfile_xyz.
#     relative path will therefore not work.
#   - !?! make be this is some kind of profisioning which is supposed to be done be ansible.
#
FROM ubuntu:bionic-20200713
ARG APT_PROXY
ENV DEBIAN_FRONTEND noninteractive


RUN    if [ $APT_PROXY ]; then echo "######################## Will configure Apt Cacher NG as Proxy: $APT_PROXY"; fi \
    && if [ $APT_PROXY ]; then sed -i 's/https:\/\//http:\/\/HTTPS\/\/\//' /etc/apt/sources.list; fi \
    && if [ $APT_PROXY ]; then echo  "Acquire::http::Proxy \"$APT_PROXY\";" | tee /etc/apt/apt.conf.d/00aptproxy ; fi \
    && apt-get update \
    && apt-get install -y python3 python3-pip sudo bash ca-certificates iproute2 python3-apt aptitude \
    && apt-get clean \
    && python3 -m pip install -U pip \
    && python3 -m pip install -U cryptography \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /etc/apt/apt.conf.d/00aptproxy \
    ;

COPY .download/spire-0.10.1/bin/spire-server /opt/spire/bin/spire-server
COPY server.conf /etc/spire-server/server.conf

CMD /opt/spire/bin/spire-server run -config /etc/spire-server/server.conf -logLevel 'debug'