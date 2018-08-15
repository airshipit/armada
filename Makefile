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
DOCKER_REGISTRY   ?= quay.io
IMAGE_PREFIX      ?= airshipit
IMAGE_NAME        ?= armada
IMAGE_TAG         ?= latest
HELM              ?= helm
PROXY             ?= http://proxy.foo.com:8000
NO_PROXY          ?= localhost,127.0.0.1,.svc.cluster.local
USE_PROXY         ?= false
PUSH_IMAGE        ?= false
LABEL             ?= commit-id
PYTHON            = python3
CHARTS            := $(patsubst charts/%/.,%,$(wildcard charts/*/.))
IMAGE             := ${DOCKER_REGISTRY}/${IMAGE_PREFIX}/${IMAGE_NAME}:${IMAGE_TAG}
PYTHON_BASE_IMAGE ?= python:3.5

# VERSION INFO
GIT_COMMIT = $(shell git rev-parse HEAD)
GIT_SHA    = $(shell git rev-parse --short HEAD)
GIT_TAG    = $(shell git describe --tags --abbrev=0 --exact-match 2>/dev/null)
GIT_DIRTY  = $(shell test -n "`git status --porcelain`" && echo "dirty" || echo "clean")

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

.PHONY: all
all: lint charts images

.PHONY: build
build: bootstrap
	$(PYTHON) setup.py install

.PHONY: bootstrap
bootstrap:
	pip install -r requirements.txt

.PHONY: bootstrap-all
bootstrap-all: bootstrap
	pip install -r test-requirements.txt

.PHONY: check-docker
check-docker:
	@if [ -z $$(which docker) ]; then \
		echo "Missing \`docker\` client which is required for development"; \
		exit 2; \
	fi

.PHONY: check-tox
check-tox:
	@if [ -z $$(which tox) ]; then \
		echo "Missing \`tox\` client which is required for development"; \
		exit 2; \
	fi

.PHONY: images
images: check-docker build_armada

.PHONY: dry-run
dry-run: clean
	tools/helm_tk.sh $(HELM)
	$(HELM) dep up charts/$(CHART)
	$(HELM) template charts/$(CHART)

.PHONY: docs
docs: build_docs

.PHONY: run_images
run_images: run_armada

.PHONY: run_armada
run_armada: build_armada
	./tools/armada_image_run.sh $(IMAGE)

.PHONY: build_docs
build_docs:
	tox -e docs

.PHONY: build_armada
build_armada:
ifeq ($(USE_PROXY), true)
	docker build --network host -t $(IMAGE) --label $(LABEL) -f ./Dockerfile \
		--build-arg FROM=$(PYTHON_BASE_IMAGE) \
		--build-arg http_proxy=$(PROXY) \
		--build-arg https_proxy=$(PROXY) \
		--build-arg HTTP_PROXY=$(PROXY) \
		--build-arg HTTPS_PROXY=$(PROXY) \
		--build-arg no_proxy=$(NO_PROXY) \
		--build-arg NO_PROXY=$(NO_PROXY) .
else
	docker build --network host -t $(IMAGE) --label $(LABEL) -f ./Dockerfile \
		--build-arg FROM=$(PYTHON_BASE_IMAGE) .
endif
ifeq ($(PUSH_IMAGE), true)
	docker push $(IMAGE)
endif

# make tools
.PHONY: protoc
protoc:
	@tools/helm-hapi.sh

.PHONY: clean
clean:
	rm -rf build
	rm -f charts/*.tgz
	rm -f charts/*/requirements.lock
	rm -rf charts/*/charts

# testing checks
.PHONY: tests
tests: check-tox
	tox

.PHONY: test-all
test-all: check-tox helm_lint
	tox

.PHONY: test-unit
test-unit: check-tox
	tox -e py35

.PHONY: test-coverage
test-coverage: check-tox
	tox -e cover

.PHONY: test-bandit
test-bandit: check-tox
	tox -e bandit

# style checks
.PHONY: lint
lint: test-pep8 helm_lint

.PHONY: test-pep8
test-pep8: check-tox
	tox -e pep8

chartbanner:
	@echo Building charts: $(CHARTS)

.PHONY: charts
charts: $(CHARTS)
	@echo Done building charts.

.PHONY: helm-init
helm-init: $(addprefix helm-init-,$(CHARTS))

.PHONY: helm-init-%
helm-init-%: helm-serve
	@echo Initializing chart $*
	cd charts;if [ -s $*/requirements.yaml ]; then echo "Initializing $*";$(HELM) dep up $*; fi

.PHONY: helm-serve
helm-serve:
	./tools/helm_tk.sh $(HELM) $(HELM_PIDFILE)

.PHONY: helm-lint
helm-lint: $(addprefix helm-lint-,$(CHARTS))

.PHONY: helm-lint-%
helm-lint-%: helm-init-%
	@echo Linting chart $*
	cd charts;$(HELM) lint $*

.PHONY: dry-run
dry-run: $(addprefix dry-run-,$(CHARTS))

.PHONY: dry-run-%
dry-run-%: helm-lint-%
	echo Running Dry-Run on chart $*
	cd charts;$(HELM) template --set pod.resources.enabled=true $*

.PHONY: $(CHARTS)
$(CHARTS): $(addprefix dry-run-,$(CHARTS)) chartbanner
	$(HELM) package -d charts charts/$@
