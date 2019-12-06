#!/bin/bash

# Copyright 2020 AT&T Intellectual Property.  All other rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

set -xe

EXAMPLE=$1

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

export NAMESPACE=test
export SERVICE_ACCOUNT=test-armada
export KUBE_CONFIG=~/.kube/config
export RELEASE_PREFIX=test
export JOB_NAME=apply-chart-test
export IMAGE=quay.io/airshipit/armada:latest-ubuntu_bionic
TIMEOUT=300
# See https://stackoverflow.com/a/24964089
export DOLLAR="\$"

# Cleanup any previous runs
cleanup() {
  kubectl delete namespace $NAMESPACE --ignore-not-found=true
  for i in $(helm ls --short | grep $RELEASE_PREFIX-); do helm del --purge $i; done
}
cleanup

# Install namespace
envsubst < $DIR/test-namespace.yaml | kubectl apply -f -
# Install CRD
kubectl apply -k ./manifests
# Install RBAC
envsubst < $DIR/test-rbac.yaml | kubectl apply -f -
# Install example CRs
kubectl apply -R -f $DIR/examples/$EXAMPLE

# Run test
export CHARTS=$(kubectl get armadacharts -n $NAMESPACE -o name | cut -d / -f2)
export CHARTS_SPACE_SEPARATED=$(echo "$CHARTS" | tr "\n" " ")

envsubst < $DIR/test-job.yaml | kubectl create -f -
# Wait for test job completion
kubectl wait --timeout ${TIMEOUT}s --for=condition=Complete -n $NAMESPACE job/$JOB_NAME
POD_NAME=$(kubectl get pods -n $NAMESPACE -l job-name=$JOB_NAME -o json | jq -r '.items[0].metadata.name')
kubectl logs -n $NAMESPACE $POD_NAME

ACTUAL=$(helm ls --short)
EXPECTED=$(echo "$CHARTS" | sed -e "s/^/$RELEASE_PREFIX-/")
diff <(echo "$ACTUAL") <(echo "$EXPECTED")
