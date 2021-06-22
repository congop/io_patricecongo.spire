# Amazon AWS Collection
The Ansible io.patricecongo.spire collection provides modules to help automate the management of [Spire](https://github.com/spiffe/spire).

## Ansible version compatibility
This collection has been tested against following Ansible versions: >=2.9.10 <2.12.0.

## Python version compatibility
Python version: >=3.6.9

Libraries:
  - pyhcl==0.4.4
  - @see: requirements.in

## OS platform compatibility
The spire-server and spire-agent are run as systemd service. The target OS must provide a working systemd environment.

## Included Modules
Name | Description
--- | ---
[io_patricecongo.spire.spire_agent](./doc/io_patricecongo.spire.spire_agent_module.rst)|Provision a spire-agent.
[io_patricecongo.spire.spire_agent_info](./doc/io_patricecongo.spire.spire_agent_module.rst)|Gather info about a spire-agent installation.
[io_patricecongo.spire.spire_agent_registration_info](./doc/io_patricecongo.spire.spire_agent_module.rst)|Returns a list of the registration entries matching the given criteria.
[io_patricecongo.spire.spire_server](./doc/io_patricecongo.spire.spire_agent_module.rst)|Provisions a spire-server.
[io_patricecongo.spire.spire_server_info](./doc/io_patricecongo.spire.spire_agent_module.rst)|Gather info about a spire-server installation
[io_patricecongo.spire.spire_spiffe_id](./doc/io_patricecongo.spire.spire_agent_module.rst)|Ensure spiffe-ID is present or absent

## Installing this collection
This collection is not available on Ansible Galaxy yet.

Therefore you will have to perform the installation using the file package:
  - cd dir-of-io_patricecongo.spire-distribution
  - ansible-galaxy collection install io_patricecongo-spire-0.1.0.tar.gz

To install the required runtime python dependencies:
  - python -m pip install requirements.txt

## Using this collection
Use ansible-doc for more info. E.g.:
  - ANSIBLE_COLLECTIONS_PATH=$(PJT_BASE)/.tmp-inst-collection/ ansible-doc

This supposes that the collection is installed at $(PJT_BASE)/.tmp-inst-collection/ E.g.:
- cd $(PJT_BASE)/
- ansible-galaxy collection install io_patricecongo-spire-0.1.0.tar.gz -p .tmp-inst-collection/


## See Also:
- [SPIFFE](https://spiffe.io/)
- [Ansible Using collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html).


## Contributing to this collection
You are welcome to add more greatness to this project. Here some things you could do:

- use it
- write about it
- give your feedback
- reports an issue
- suggest a missing feat ure
- send pull requests (please discuss your change first by raising an issue)
- etc.

## How to Dev
- Development platform requirement
  - ensure make and tree are installed
- ensure docker are installed
- Project setup
  - Clone
    - https://github.com/congop/io_patricecongo.spire
  - create fake src directory structure to make collection python module easy to use while developing
    - make dev-local-fake-src-for-ansible-collections
  - create virtual environment
    - make dev-create-venv_2_9
    - make dev-create-venv_2_10
    - make dev-create-venv_2_11
  - cache spire distribution locally
    - make -f molecule/resources/docker-spire-server/Makefile spire-distribution-cached-locally
  - Make docker images for molecule tests
    - make -f molecule/resources/docker-spire-server/Makefile docker-build-all-images
- Run unit test
  - make dev-pytest-all-local_2_9
  - make dev-pytest-all-local_2_10
  - make dev-pytest-all-local_2_11
- Run molecule test
  - make dev-ansible-galaxy-dist
  - make dev-molecule-all-local_2_9
  - make dev-molecule-all-local_2_10
  - make dev-molecule-all-local_2_11
- Enjoy Coding with your favorite IDE
  - e.g. Visual Studio Code
    - code .
- Try github action locally
  - Ensure act binary is available at .tmp/bin/act
    - @see https://github.com/nektos/act
    - make act-install-binary
  - Build specialized image for our systemd requirements
    - make docker-build-act-runner
  - run ci.yml locally
    make act-run-github-actions-job-build


# Licensing

GNU General Public License v3.0 or later.

See [COPYING](https://www.gnu.org/licenses/gpl-3.0.txt) to see the full text.