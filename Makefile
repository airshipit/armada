# Copyright 2018 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# APP INFO
BUILD_DIR         := $(shell mktemp -d)
DOCKER_REGISTRY   ?= quay.io
IMAGE_PREFIX      ?= airshipit
IMAGE_NAME        ?= armada
IMAGE_TAG         ?= latest
HELM              ?= $(BUILD_DIR)/helm
PROXY             ?= http://proxy.foo.com:8000
NO_PROXY          ?= localhost,127.0.0.1,.svc.cluster.local
USE_PROXY         ?= false
PUSH_IMAGE        ?= false
# use this variable for image labels added in internal build process
LABEL             ?= org.airshipit.build=community
COMMIT            ?= $(shell git rev-parse HEAD)
PYTHON            = python3
CHARTS            := $(patsubst charts/%/.,%,$(wildcard charts/*/.))
DISTRO            ?= ubuntu_bionic
IMAGE             := ${DOCKER_REGISTRY}/${IMAGE_PREFIX}/${IMAGE_NAME}:${IMAGE_TAG}-${DISTRO}
UBUNTU_BASE_IMAGE ?=

# VERSION INFO
GIT_COMMIT = $(shell git rev-parse HEAD)
GIT_SHA    = $(shell git rev-parse --short HEAD)
GIT_TAG    = $(shell git describe --tags --abbrev=0 --exact-match 2>/dev/null)
GIT_DIRTY  = $(shell test -n "`git status --porcelain`" && echo "dirty" || echo "clean")

HELM_PIDFILE ?= $(abspath ./.helm-pid)

ifdef VERSION
	DOCKER_VERSION = $(VERSION)
endif

SHELL = /bin/bash

info:
	@echo "Version:           ${VERSION}"
	@echo "Git Tag:           ${GIT_TAG}"
	@echo "Git Commit:        ${GIT_COMMIT}"
	@echo "Git Tree State:    ${GIT_DIRTY}"
	@echo "Docker Version:    ${DOCKER_VERSION}"
	@echo "Registry:          ${DOCKER_REGISTRY}"

all: lint charts images

build: bootstrap
	$(PYTHON) setup.py install

bootstrap:
	pip install -r requirements.txt

bootstrap-all: bootstrap
	pip install -r test-requirements.txt

check-docker:
	@if [ -z $$(which docker) ]; then \
		echo "Missing \`docker\` client which is required for development"; \
		exit 2; \
	fi

check-tox:
	@if [ -z $$(which tox) ]; then \
		echo "Missing \`tox\` client which is required for development"; \
		exit 2; \
	fi

images: check-docker build_armada

docs: clean build_docs

build_docs:
	tox -e docs

run_images: run_armada

run_armada: build_armada
	./tools/armada_image_run.sh $(IMAGE)

_BASE_IMAGE_ARG := $(if $(UBUNTU_BASE_IMAGE),--build-arg FROM="${UBUNTU_BASE_IMAGE}" ,)

build_armada:
ifeq ($(USE_PROXY), true)
	docker build --network host -t $(IMAGE) --label $(LABEL) \
		--label "org.opencontainers.image.revision=$(COMMIT)" \
		--label "org.opencontainers.image.created=$(shell date --rfc-3339=seconds --utc)" \
		--label "org.opencontainers.image.title=$(IMAGE_NAME)" \
		-f images/armada/Dockerfile.$(DISTRO) \
		$(_BASE_IMAGE_ARG) \
		--build-arg http_proxy=$(PROXY) \
		--build-arg https_proxy=$(PROXY) \
		--build-arg HTTP_PROXY=$(PROXY) \
		--build-arg HTTPS_PROXY=$(PROXY) \
		--build-arg no_proxy=$(NO_PROXY) \
		--build-arg NO_PROXY=$(NO_PROXY) .
else
	docker build --network host -t $(IMAGE) --label $(LABEL) \
		--label "org.opencontainers.image.revision=$(COMMIT)" \
		--label "org.opencontainers.image.created=$(shell date --rfc-3339=seconds --utc)" \
		--label "org.opencontainers.image.title=$(IMAGE_NAME)" \
		-f images/armada/Dockerfile.$(DISTRO) \
		$(_BASE_IMAGE_ARG) .
endif
ifeq ($(PUSH_IMAGE), true)
	docker push $(IMAGE)
endif

# make tools
protoc:
	@tools/helm-hapi.sh

clean:
	rm -rf build
	rm -rf doc/build
	rm -f charts/*.tgz
	rm -f charts/*/requirements.lock
	rm -rf charts/*/charts

# testing checks
tests: check-tox
	tox

test-all: check-tox helm_lint
	tox

test-unit: check-tox
	tox -e py35

test-coverage: check-tox
	tox -e cover

test-bandit: check-tox
	tox -e bandit

# Perform auto formatting
format:
	tox -e fmt

# style checks
lint: test-pep8 helm_lint

test-pep8: check-tox
	tox -e pep8

chartbanner:
	@echo Building charts: $(CHARTS)

charts: $(CHARTS)
	@echo Done building charts.

helm-init: $(addprefix helm-init-,$(CHARTS))

helm-init-%: helm-serve
	@echo Initializing chart $*
	cd charts;if [ -s $*/requirements.yaml ]; then echo "Initializing $*";$(HELM) dep up $*; fi

helm-serve: helm-install
	./tools/helm_tk.sh $(HELM) $(HELM_PIDFILE)

helm-lint: $(addprefix helm-lint-,$(CHARTS))

helm-lint-%: helm-init-%
	@echo Linting chart $*
	cd charts;$(HELM) lint $*

dry-run: clean $(addprefix dry-run-,$(CHARTS))

dry-run-%: helm-lint-%
	echo Running Dry-Run on chart $*
	cd charts;$(HELM) template --set pod.resources.enabled=true $*

$(CHARTS): $(addprefix dry-run-,$(CHARTS)) chartbanner
	$(HELM) package -d charts charts/$@

# Install helm binary
helm-install:
	./tools/helm_install.sh $(HELM)

.PHONY: $(CHARTS) all bootstrap bootstrap-all build build_armada \
  build_docs charts check-docker check-tox clean docs dry-run \
  dry-run-% format helm-init helm-init-% helm-install helm-lint \
  helm-lint-% helm-serve images lint protoc run_armada run_images \
  test-all test-bandit test-coverage test-pep8 tests test-unit
