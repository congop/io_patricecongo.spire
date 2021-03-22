SHELL = /bin/bash

THIS_LIST := $(MAKEFILE_LIST)
THIS_DIR := $(dir $(abspath $(firstword $(MAKEFILE_LIST))))

MKFILE_ABSPATH := $(abspath $(lastword $(MAKEFILE_LIST)))
MKFILE_ABSDIR := $(strip $(patsubst %/,%,$(dir $(MKFILE_ABSPATH))) )
	#no trailling / and <space>

SPIRE_VERSION=0.10.1
SPIRE_DOWNLOAD_FILE_NAME=spire-$(SPIRE_VERSION)-linux-x86_64-glibc.tar.gz

SPIRE_VERSION_2=0.11.2
SPIRE_DOWNLOAD_FILE_NAME_2=spire-$(SPIRE_VERSION_2)-linux-x86_64-glibc.tar.gz

DOWNLOAD_DIR=$(MKFILE_ABSDIR)/.download
#v0.10.0.tar.gz
#https://github.com/spiffe/spire/archive/v0.10.0.tar.gz
#https://github.com/spiffe/spire/archive/v0.9.2.tar.gz

#https://github.com/spiffe/spire/releases/download/v0.10.0/spire-0.10.0-linux-x86_64-glibc.tar.gz
#https://github.com/spiffe/spire/releases/download/v0.10.0/spire-0.10.0-linux-x86_64-glibc.tar.gz

# ddd:
# 	echo $(THIS_LIST)
# 	echo $(THIS_DIR)
# 	echo $(current_dir)

spire-distribution-cached-locally: spire-distribution-download spire-distribution-extract

spire-distribution-download: $(DOWNLOAD_DIR)/${SPIRE_DOWNLOAD_FILE_NAME} $(DOWNLOAD_DIR)/${SPIRE_DOWNLOAD_FILE_NAME_2}

$(DOWNLOAD_DIR)/${SPIRE_DOWNLOAD_FILE_NAME}:
	mkdir -p $(DOWNLOAD_DIR)
	curl -SL https://github.com/spiffe/spire/archive/{$(SPIRE_DOWNLOAD_FILE_NAME)} -o "$(DOWNLOAD_DIR)/#1"
	curl -SL https://github.com/spiffe/spire/releases/download/v$(SPIRE_VERSION)/{$(SPIRE_DOWNLOAD_FILE_NAME)} -o "$(DOWNLOAD_DIR)/#1"

$(DOWNLOAD_DIR)/${SPIRE_DOWNLOAD_FILE_NAME_2}:
	mkdir -p $(DOWNLOAD_DIR)
	curl -SL https://github.com/spiffe/spire/archive/{$(SPIRE_DOWNLOAD_FILE_NAME_2)} -o "$(DOWNLOAD_DIR)/#1"
	curl -SL https://github.com/spiffe/spire/releases/download/v$(SPIRE_VERSION_2)/{$(SPIRE_DOWNLOAD_FILE_NAME_2)} -o "$(DOWNLOAD_DIR)/#1"

spire-distribution-extract: $(DOWNLOAD_DIR)/spire-${SPIRE_VERSION}/bin/spire-server $(DOWNLOAD_DIR)/spire-${SPIRE_VERSION_2}/bin/spire-server

#	[ -f ./spire-${VERSPIRE_VERSIONSION}/bin/spire-server ] &&

$(DOWNLOAD_DIR)/spire-${SPIRE_VERSION}/bin/spire-server:
	tar -xzf $(DOWNLOAD_DIR)/$(SPIRE_DOWNLOAD_FILE_NAME) -C $(DOWNLOAD_DIR)

$(DOWNLOAD_DIR)/spire-${SPIRE_VERSION_2}/bin/spire-server:
	tar -xzf $(DOWNLOAD_DIR)/$(SPIRE_DOWNLOAD_FILE_NAME_2) -C $(DOWNLOAD_DIR)

clean:
	rm -rf $(MKFILE_ABSDIR)/.download

docker-copy-rquirements-txt-to-context:
	mkdir -p $(MKFILE_ABSDIR)/.download/
	cp -f $(MKFILE_ABSDIR)/../../../requirements.txt $(MKFILE_ABSDIR)/.download/requirements.txt

docker-build-spire-server: docker-copy-rquirements-txt-to-context
	cd $(MKFILE_ABSDIR) \
	&& IMG_SPIRE_SERVER_FOUND='$(shell docker image ls molecule_local/ubuntu-spire-server --format "{{.ID}}: {{.Repository}}")' \
	&& 	if [[ -n $$IMG_SPIRE_SERVER_FOUND ]]; then \
				echo "Image [ $$IMG_SPIRE_SERVER_FOUND ] found --> skipping docker build"; \
			else \
				docker build . -t molecule_local/ubuntu-spire-server; \
			fi

docker-build-ubuntu-py3: docker-copy-rquirements-txt-to-context
	cd $(MKFILE_ABSDIR) \
	&& IMG_UBUNTU_PY3='$(shell docker image ls molecule_local/ubuntu-py3 --format "{{.ID}}: {{.Repository}}")' \
	&& 	if [[ -n $$IMG_UBUNTU_PY3 ]]; then \
				echo "Image [ $$IMG_UBUNTU_PY3 ] found --> skipping docker build"; \
			else \
				docker build -f ./Dockerfile.ubuntu-py3 -t molecule_local/ubuntu-py3 .; \
			fi

docker-build-all-images: docker-build-spire-server docker-build-ubuntu-py3

docker-rm-all-built-images:
	cd $(MKFILE_ABSDIR) \
	&& IMG_UBUNTU_PY3='$(shell docker image ls molecule_local/ubuntu-py3 --format "{{.ID}}: {{.Repository}}")' \
	&& 	if [[ -n $$IMG_UBUNTU_PY3 ]]; then \
				docker image rm molecule_local/ubuntu-py3; \
			fi \
	&& IMG_SPIRE_SERVER_FOUND='$(shell docker image ls molecule_local/ubuntu-spire-server --format "{{.ID}}: {{.Repository}}")' \
	&& 	if [[ -n $$IMG_SPIRE_SERVER_FOUND ]]; then \
				docker image rm molecule_local/ubuntu-spire-server; \
			fi