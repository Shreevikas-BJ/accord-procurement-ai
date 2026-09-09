#!/bin/sh
set -eu
mkdir -p /app/data/uploads
chown procurement:procurement /app/data/uploads
exec gosu procurement "$@"
