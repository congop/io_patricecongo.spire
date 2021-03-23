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

# Make assumption
# - ansible 2.10.x ist the dev version and actual target version
#   This version is used by default (i.e. when not version hint is given)
# - ansible 2.9.x which is the "current" previous version is supported too
#   as similar to the support ansible tool generally give.
# Dev platform
#	  - Python3 with ansible, installed using make tool
#   - the required dev dependencies are specified in [dev-]requirements.in
#     - They are compiled with piptools.
#     - But installed using pip tih <-r> and not piptools-synch as
#       sync will remove libs from the virtual env that are not present in requirement.
#       This removing some libraries from the base platform.
# Usage:
#   - create fake src directory structure to make collection python module
#     easy to use while developing
#     - make dev-local-fake-src-for-ansible-collections
#   - create virtual environment
#     make dev-create-venv_2_9
#     make make dev-create-venv_2_10
#   - run unit test
#     make dev-pytest-all-local_2_9
#     make dev-pytest-all-local_2_10
#   - run molecule test
#     make make dev-ansible-galaxy-dist ## make collection distribution
#     make dev-molecule-all-local_2_9
#     make dev-molecule-all-local_2_10

#python -m pip install --upgrade pip setuptools wheel
SHELL = /bin/bash

#THIS_LIST := $(MAKEFILE_LIST)
#THIS_DIR := $(dir $(abspath $(firstword $(MAKEFILE_LIST))))

PJT_MKFILE_ABSPATH := $(abspath $(lastword $(MAKEFILE_LIST)))
PJT_MKFILE_ABSDIR := $(strip $(patsubst %/,%,$(dir $(PJT_MKFILE_ABSPATH))) )

FAKE_SRC_DIR = $(PJT_MKFILE_ABSDIR)/__fake_src
FAKE_SRC_DIR_STUBS = $(FAKE_SRC_DIR)_stubs

# issue the collection project structure mandate the following structure:
#
# It also requires to import the plugins package/module and classes using percular format:
# ansible_collections/<namespace>/<collection_name>/...
# e.g.: from ansible_collections.io_patricecongo.spire.plugins.module_utils import spire_server_entry_cmd
# Ansible has its now module/package/class loading mechanism which enable it to discover those
# modules/packages and class under the required path format.
# Normale python tools (python, code python extensions, mypy)  will not find them.
# The help:
#   -0- provide a loading mechanism (@see SpireCollectionLoader and SpireCollectionFinder for testing)
#		-1- or make the directory structure + adding it the PYTHONPATH
#  This make rule implements strategy 1
dev-local-fake-src-for-ansible-collections:
	mkdir -p $(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins
	ln -s -r plugins/module_utils -t $(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins
	ln -s -r plugins/modules -t $(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins
	ln -s -r plugins/action -t $(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins
	touch \
			$(FAKE_SRC_DIR)/ansible_collections/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins/__init__.py \

dev-local-mypy-stubs-clean-in-fake_src:
	find -L $(FAKE_SRC_DIR) -iname "*.pyi" -delete
	find -L $(FAKE_SRC_DIR) -iname "py.typed" -delete
	@tree -l $(FAKE_SRC_DIR)

#Mixxing stub files and runtime files
dev-local-make-mypy-stubs:
	find -L $(FAKE_SRC_DIR) -iname "*.pyi" -delete
	find -L $(FAKE_SRC_DIR) -iname "py.typed" -delete
	@tree -l $(FAKE_SRC_DIR)
	source .venv_2_10/bin/activate \
	&& python --version \
	&& touch \
			$(FAKE_SRC_DIR)/ansible_collections/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/__init__.py \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins/__init__.py \
	&& touch \
			$(FAKE_SRC_DIR)/ansible_collections/py.typed \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/py.typed \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/py.typed \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins/py.typed \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins/module_utils/py.typed \
			$(FAKE_SRC_DIR)/ansible_collections/io_patricecongo/spire/plugins/modules/py.typed \
	&& PYTHONPATH=$(FAKE_SRC_DIR) stubgen -p ansible_collections -o $(FAKE_SRC_DIR) -vv \
	&& PYTHONPATH=$(FAKE_SRC_DIR) stubgen -p ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd -o $(FAKE_SRC_DIR) -vv \
	;
	@tree -l $(FAKE_SRC_DIR)
	@echo DONE!!

dev-local-make-mypy-stubs-only-dir:
	mkdir -p $(FAKE_SRC_DIR_STUBS)
	find -L $(FAKE_SRC_DIR_STUBS) -iname "*.pyi" -delete
	find -L $(FAKE_SRC_DIR_STUBS) -iname "py.typed" -delete
	@tree -l $(FAKE_SRC_DIR_STUBS)
	source .venv/bin/activate \
	&& python --version \
	&& PYTHONPATH=$(FAKE_SRC_DIR) stubgen -p ansible_collections -o $(FAKE_SRC_DIR_STUBS) -vv \
	&& PYTHONPATH=$(FAKE_SRC_DIR) stubgen -p ansible_collections.io_patricecongo.spire.plugins.module_utils.spire_server_entry_cmd -o $(FAKE_SRC_DIR_STUBS) -vv \
	;
	@tree -l $(FAKE_SRC_DIR_STUBS)
	@echo DONE!!

dev-venv:
	python3 -m venv .venv_2_10

dev-venv-terminal-activate:
	source .venv_2_10/bin/activate && \
	python --version

#pip-tools = pip-compile + pip-sync
dev-install-tools:
	python3 -m pip install -U pip-tools
#pip freeze > requirements.txt
dev-build-requirements:
	python3 -m piptools compile requirements.in
	python3 -m piptools compile dev-requirements.in
	python3 -m pip install -r requirements.txt
	python3 -m pip install -r dev-requirements.txt

dev-pytest-all-local_2_9:
	. .venv_2_9/bin/activate && \
	python --version && \
	export readiness_probe_timeout_seconds=10.0 && \
	PYTHONPATH=plugins/:__fake_src python -m pytest -vv tests/**.py

dev-pytest-all-local_2_10:
	. .venv_2_10/bin/activate && \
	python --version && \
	export readiness_probe_timeout_seconds=10.0 && \
	PYTHONPATH=plugins/:__fake_src python -m pytest -vv tests/**.py

# path in pythonpath have to be absolute:
#		otherwise the ansible_collections in test-infra cannot be discovered
dev-molecule-all-local_2_9:
	build-tools/ensure-local-bridge-network-available.sh molecule-net && \
	source .venv_2_9/bin/activate && \
	python --version && \
	PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/tests \
		molecule -c $(PJT_MKFILE_ABSDIR)/molecule/resources/base_molecule.yml test --all

dev-molecule-all-local_2_10:
	build-tools/ensure-local-bridge-network-available.sh molecule-net && \
	source .venv_2_10/bin/activate && \
	python --version && \
	PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/tests \
		molecule -c $(PJT_MKFILE_ABSDIR)/molecule/resources/base_molecule.yml test --all

MOL_DESTROY ?= always
dev-molecule-all-local_2_10_scenario:
	export mol_scenario="$(MOL_SCENARIO)" && if [[ -z "$${mol_scenario//[[:space:]]}" ]]; then  \
			echo -e "\nPlease provide MOL_SCENARIO:"; \
			echo -e "\tmake dev-molecule-all-local_2_10_scenario MOL_SCENARIO=xxxxxxx [MOL_DESTROY=always|never] \n"; \
			exit -1; \
		fi
	. .venv_2_10/bin/activate && \
	python --version && \
	PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/tests \
		molecule -c $(PJT_MKFILE_ABSDIR)/molecule/resources/base_molecule.yml -vvv --debug test \
		-s "$(MOL_SCENARIO)" --destroy "$(MOL_DESTROY)"

dev-molecule-all-local_2_10_scenario_destroy:
	export mol_scenario="$(MOL_SCENARIO)" && if [[ -z "$${mol_scenario//[[:space:]]}" ]]; then  \
			echo -e "\nPlease provide MOL_SCENARIO:"; \
			echo -e "\tmake dev-molecule-all-local_2_10_scenario MOL_SCENARIO=xxxxxxx\n"; \
			exit -1; \
		fi
	. .venv_2_10/bin/activate && \
	python --version && \
	PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/tests \
		molecule -c $(PJT_MKFILE_ABSDIR)/molecule/resources/base_molecule.yml -vvv destroy \
		-s "$(MOL_SCENARIO)"

dev-mypy-type-checking_2_9:
	#PYTHONPATH=plugins/:.fake_src tox -e mypy
	cd $(PJT_MKFILE_ABSDIR) \
	&& . .venv_2_9/bin/activate \
	&& python --version \
	&& PFILES=$$(find -L __fake_src/ -iname "*.py"); \
			PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/.venv_2_9/lib/python3.6/site-packages/ \
			tox -e mypy -- $$(echo $${PFILES}) --strict --show-error-codes \
	;

dev-mypy-type-checking_2_10:
	#PYTHONPATH=plugins/:.fake_src tox -e mypy
	# 	MYPYPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/.venv_2_10/lib/python3.6/site-packages/
	cd $(PJT_MKFILE_ABSDIR) \
	&& . .venv_2_10/bin/activate \
	&& python --version \
	&& PFILES=$$(find -L __fake_src/ -iname "*.py"); \
			PYTHONPATH=$(FAKE_SRC_DIR):$(PJT_MKFILE_ABSDIR)/tests:$(PJT_MKFILE_ABSDIR)/.venv_2_10/lib/python3.6/site-packages/ \
			tox -e mypy -- $$(echo $${PFILES}) --strict --show-error-codes \
	;

# for the ignore mechanism of version 2.10 still in dev
# molecule does not play well with devel ansible (which seems to be ansible-base only)
# so we are having a 2nd venv to provide ansible-galaxy for packaging this collection
# TODO revisite after ansible 2.10 release
dev-create-venv-devel:
	python3 -m venv .venv_devel && \
	. .venv_devel/bin/activate && \
	python -m pip install -U pip && \
	python -m pip install ../ansible-2.10.0rc4.tar.gz;

#python -m pip install -r dev-requirements.txt
dev-create-venv_2_10:
	if [[ ! -f .venv_2_10/bin/activate ]]; then python3 -m venv .venv_2_10; fi && \
	. .venv_2_10/bin/activate && \
	python -m pip install -U pip && \
	python -m pip install ansible~=2.10.0 && \
	make dev-install-tools && \
	make dev-build-requirements

dev-create-venv_2_9:
	if [[ ! -f .venv_2_9/bin/activate ]]; then python3 -m venv .venv_2_9; fi && \
	. .venv_2_9/bin/activate && \
	python -m pip install -U pip && \
	python -m pip install ansible~=2.9.0 && \
	make dev-install-tools && \
	make dev-build-requirements

# using ansible-2.10.x
# which have better ignore mechanism
dev-ansible-galaxy-dist:
	cd $(PJT_MKFILE_ABSDIR) && \
	. .venv_2_10/bin/activate && \
	python --version && \
	ansible --version && \
	ansible-galaxy collection build . --force && \
	ls -l -h io_patricecongo-spire-0.1.0.tar.gz  && \
	rm -rf .tmp-inst-collection/* && \
	mkdir -p .tmp-inst-collection/  && \
	ansible-galaxy collection install io_patricecongo-spire-0.1.0.tar.gz -p .tmp-inst-collection/

#MODULE_FQN ?= always
dev-ansible-doc:
	export mod_fqn="$(MODULE_FQN)" && if [[ -z "$${mod_fqn//[[:space:]]}" ]]; then  \
			echo -e "\nPlease provide MODULE_FQN:"; \
			echo -e "\tmake dev-ansible-doc MODULE_FQN=xxxxxxx(e.g io_patricecongo.spire.spire_spiffe_id)  \n"; \
			source .venv_2_10/bin/activate && ANSIBLE_COLLECTIONS_PATH=$(PJT_MKFILE_ABSDIR)/.tmp-inst-collection/ ansible-doc -l io_patricecongo.spire ; \
			exit -1; \
		fi
	. .venv_2_10/bin/activate && \
	python --version && \
	ANSIBLE_COLLECTIONS_PATH=$(PJT_MKFILE_ABSDIR)/.tmp-inst-collection/ ansible-doc $(MODULE_FQN)




dev-local-dist-tar-gz-list-levl-1:
	tar -tvf io_patricecongo-spire-0.1.0.tar.gz | grep -v -E ".*/.*/.*/.*|.*/.*/.+.py" -

# without watchman
dev-pyre-install:
	cd $(PJT_MKFILE_ABSDIR) \
	&& . .venv_2_10/bin/activate \
	&& python --version \
	&& python -m pip install -U pyre-check \
	&& if [[ ! -f .pyre_configuration ]]; then pyre init; fi \
	;

dev-pyre-type-check:
	cd $(PJT_MKFILE_ABSDIR) \
	&& . .venv_2_10/bin/activate \
	&& python --version \
	&& pyre \
	;

#@ if [[ -z "${search_pattern//[[:space:]]}" ]]; then  echo -e "\nPlease provide search_pattern:\n \tmake dev-grep-ansile-python earch_pattern=xxxxxxx\n"; exit -1; fi
dev-grep-ansile-python:
	export search_pattern="$(search_pattern)" && if [[ -z "$${search_pattern//[[:space:]]}" ]]; then  \
			echo -e "\nPlease provide search_pattern:"; \
			echo -e "\tmake dev-grep-ansile-python earch_pattern=xxxxxxx\n"; \
			exit -1; \
		fi
	grep -r .venv_2_10/lib/python3.6/site-packages/ansible/ --include "*.py" -e "$(search_pattern)"  -n ; \
		grep_exit=$$? ; \
		if [[ $$grep_exit -eq 1 ]]; then \
			echo "NO Match!"; \
		elif [[ $$grep_exit -eq 0 ]]; then true; \
		else $$(exit $$grep_exit); \
		fi;

docker-build-act-runner:
	cd $(PJT_MKFILE_ABSDIR)/.act \
	&& IMG_RUNNER='$(shell docker image ls act_local/runner-ubuntu-20.4 --format "{{.ID}}: {{.Repository}}")' \
	&& 	if [[ -n $$IMG_RUNNER ]]; then \
				echo "Image [ $$IMG_RUNNER ] found --> skipping docker build"; \
			else \
				docker build -f ./Dockerfile.act-runner -t act_local/runner-ubuntu-20.4 .; \
			fi

docker-clean-act-runner-img-container:
	docker container stop act-ci-for-io-patricecongo-spire-CI-io-patricecongo-spire || true
	docker container rm act-ci-for-io-patricecongo-spire-CI-io-patricecongo-spire || true
	docker image rm -f act_local/runner-ubuntu-20.4:latest

act-install-binary:
	build-tools/install-act-bin.sh 0.2.20


act-run-github-actions-job-build:
	cd $(PJT_MKFILE_ABSDIR)
	clear ;
	.tmp/bin/act -v --env LC_ALL=C.UTF-8 \
		--env LANG=C.UTF-8 \
		--env LC_TIME=C.UTF-8 \
		--platform ubuntu-20.04=act_local/runner-ubuntu-20.4 \
		--privileged \
	;
