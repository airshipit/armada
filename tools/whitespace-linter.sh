#!/usr/bin/env bash
set -x

RES=$(git grep -E -l " +$")

if [[ -n $RES ]]; then
  exit 1
fi
