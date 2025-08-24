#!/usr/bin/env bash
set -euo pipefail
podman play kube --down metrics-pod.yml || true
echo "Down."
