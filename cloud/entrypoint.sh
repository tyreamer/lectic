#!/bin/sh
set -eu
# Render mounts the persistent disk at runtime. Only this fixed mount is initialized.
mkdir -p /var/lectic
chown 10001:10001 /var/lectic
exec gosu 10001:10001 python -m lectic.cloud.service
