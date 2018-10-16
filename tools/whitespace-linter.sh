#!/usr/bin/env bash
set -xe

RES=$(find . \
  -not -path "*/\.*" \
  -not -path "*/*.egg-info/*" \
  -not -path "*/releasenotes/build/*" \
  -not -path "*/doc/build/*" \
  -not -name "*.tgz" \
  -not -name "*.html" \
  -not -name "*.pyc" \
  -type f -exec egrep -l " +$" {} \;)

if [[ -n $RES ]]; then
  exit 1
fi
