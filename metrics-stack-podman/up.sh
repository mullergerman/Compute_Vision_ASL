#!/usr/bin/env bash
set -euo pipefail
# Replace token if provided as env var
if [[ -n "${METRICS_TOKEN:-}" ]]; then
  sed -i "s/CHANGE_ME_SUPER_TOKEN/${METRICS_TOKEN}/g" nginx/nginx.conf
fi
podman play kube metrics-pod.yml
podman ps --filter name=metrics-stack
echo "Up. Grafana: https://localhost:3000  Graphite: http://localhost:8080  Ingest: https://localhost/ingest"
