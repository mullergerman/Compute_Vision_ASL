#!/bin/bash

# Script de limpieza rápida de InfluxDB (sin confirmación)
# Para uso en desarrollo/testing

INFLUX_TOKEN="example-token"
INFLUX_ORG="example-org"
INFLUX_BUCKET="example-bucket"
CONTAINER_NAME="metrics-stack-influxdb"

echo "🧹 Limpiando bucket '$INFLUX_BUCKET'..."

# Verificar que el contenedor está corriendo
if ! podman ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Error: Contenedor InfluxDB no está ejecutándose"
    exit 1
fi

# Limpiar todos los datos
podman exec -i $CONTAINER_NAME influx delete \
    --bucket "$INFLUX_BUCKET" \
    --start "1970-01-01T00:00:00Z" \
    --stop "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --token "$INFLUX_TOKEN" \
    --org "$INFLUX_ORG" 2>/dev/null

echo "✅ Limpieza completada"
