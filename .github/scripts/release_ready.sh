#!/usr/bin/env bash

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

# Fails a release pull request, one whose last commit is 'ver: bump to v...',
# that lacks commits of its base branch, $1: release.yml publishes only the
# tree the pull request's checks ran on, so one behind cannot release

set -euo pipefail

case "$(git log -1 --format=%s)" in
  "ver: bump to v"*) ;;
  *) echo "Not a release pull request"; exit 0 ;;
esac
git fetch --quiet origin "$1"
if ! git merge-base --is-ancestor FETCH_HEAD HEAD; then
  echo "Rebase on $1 and push again: it has commits this lacks"
  exit 1
fi
