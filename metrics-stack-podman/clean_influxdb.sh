#!/bin/bash

# Script para limpiar todos los registros del bucket example-bucket en InfluxDB
# Autor: Agent Mode
# Fecha: $(date)

set -e  # Exit on any error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración InfluxDB
INFLUX_TOKEN="example-token"
INFLUX_ORG="example-org"
INFLUX_BUCKET="example-bucket"
CONTAINER_NAME="metrics-stack-influxdb"

echo -e "${BLUE}🗑️  Script de Limpieza InfluxDB${NC}"
echo -e "${BLUE}=====================================${NC}"

# Verificar que el contenedor está corriendo
echo -e "${YELLOW}📋 Verificando estado del contenedor InfluxDB...${NC}"
if ! podman ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}❌ Error: El contenedor $CONTAINER_NAME no está ejecutándose${NC}"
    echo -e "${YELLOW}💡 Para iniciar el stack: podman play kube metrics-pod.yml${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Contenedor InfluxDB está ejecutándose${NC}"

# Verificar conectividad
echo -e "${YELLOW}🔗 Verificando conectividad con InfluxDB...${NC}"
if ! wget -q -O - http://localhost:8086/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: No se puede conectar a InfluxDB en localhost:8086${NC}"
    exit 1
fi
echo -e "${GREEN}✅ InfluxDB está respondiendo${NC}"

# Mostrar registros actuales antes de limpiar
echo -e "${YELLOW}📊 Contando registros actuales en bucket '$INFLUX_BUCKET'...${NC}"
CURRENT_COUNT=$(podman exec -i $CONTAINER_NAME influx query \
    'from(bucket: "'"$INFLUX_BUCKET"'") |> range(start: -30d) |> count()' \
    --token "$INFLUX_TOKEN" --org "$INFLUX_ORG" 2>/dev/null | grep -E "^\s*[0-9]" | wc -l || echo "0")

if [ "$CURRENT_COUNT" -gt 0 ]; then
    echo -e "${BLUE}📈 Registros encontrados: $CURRENT_COUNT${NC}"
    
    # Mostrar mediciones disponibles
    echo -e "${YELLOW}📋 Mediciones disponibles:${NC}"
    podman exec -i $CONTAINER_NAME influx query \
        'import "influxdata/influxdb/schema" schema.measurements(bucket: "'"$INFLUX_BUCKET"'")' \
        --token "$INFLUX_TOKEN" --org "$INFLUX_ORG" 2>/dev/null | grep -v "Result:" | grep -v "Table:" | grep -v "^$" | sed 's/^/  - /'
else
    echo -e "${GREEN}✅ El bucket ya está vacío${NC}"
    exit 0
fi

# Confirmación del usuario
echo ""
echo -e "${RED}⚠️  ADVERTENCIA: Esta operación eliminará TODOS los datos del bucket '$INFLUX_BUCKET'${NC}"
echo -e "${YELLOW}¿Estás seguro de que quieres continuar? (y/N):${NC} "
read -r confirmation

if [[ ! "$confirmation" =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ Operación cancelada${NC}"
    exit 0
fi

# Realizar la limpieza
echo -e "${YELLOW}🧹 Limpiando bucket '$INFLUX_BUCKET'...${NC}"

# Método 1: Intentar eliminar por rango de tiempo (más rápido)
echo -e "${YELLOW}  → Eliminando datos por rango de tiempo...${NC}"
DELETE_RESULT=$(podman exec -i $CONTAINER_NAME influx delete \
    --bucket "$INFLUX_BUCKET" \
    --start "1970-01-01T00:00:00Z" \
    --stop "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --token "$INFLUX_TOKEN" \
    --org "$INFLUX_ORG" 2>&1 || true)

# Verificar si la limpieza fue exitosa
echo -e "${YELLOW}🔍 Verificando limpieza...${NC}"
sleep 2  # Esperar a que los cambios se propaguen

NEW_COUNT=$(podman exec -i $CONTAINER_NAME influx query \
    'from(bucket: "'"$INFLUX_BUCKET"'") |> range(start: -30d) |> count()' \
    --token "$INFLUX_TOKEN" --org "$INFLUX_ORG" 2>/dev/null | grep -E "^\s*[0-9]" | wc -l || echo "0")

if [ "$NEW_COUNT" -eq 0 ]; then
    echo -e "${GREEN}🎉 ¡Limpieza exitosa!${NC}"
    echo -e "${GREEN}✅ Bucket '$INFLUX_BUCKET' está ahora completamente vacío${NC}"
else
    echo -e "${YELLOW}⚠️  Algunos datos pueden permanecer. Registros restantes: $NEW_COUNT${NC}"
    echo -e "${YELLOW}💡 Esto es normal si hay datos muy recientes. Ejecuta el script nuevamente si es necesario.${NC}"
fi

# Mostrar estadísticas finales
echo ""
echo -e "${BLUE}📊 Estadísticas de Limpieza:${NC}"
echo -e "${BLUE}  • Registros antes:  $CURRENT_COUNT${NC}"
echo -e "${BLUE}  • Registros después: $NEW_COUNT${NC}"
echo -e "${BLUE}  • Eliminados:       $((CURRENT_COUNT - NEW_COUNT))${NC}"

echo ""
echo -e "${GREEN}✅ Script completado${NC}"
