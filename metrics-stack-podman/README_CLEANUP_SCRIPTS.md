# 🗑️ Scripts de Limpieza InfluxDB

Este directorio contiene scripts para limpiar completamente el bucket `example-bucket` de InfluxDB.

## 📁 Scripts Disponibles

### 1. `clean_influxdb.sh` - Script Completo e Interactivo

```bash
./clean_influxdb.sh
```

**Características:**
- ✅ **Verificaciones completas**: Estado del contenedor, conectividad
- ✅ **Estadísticas**: Muestra registros antes/después de la limpieza  
- ✅ **Confirmación de usuario**: Pide confirmación antes de eliminar
- ✅ **Output colorido**: Interfaz visual clara con colores
- ✅ **Información detallada**: Muestra mediciones disponibles
- ✅ **Manejo de errores**: Verificaciones robustas

**Uso recomendado:** Producción o cuando necesitas confirmación

### 2. `clean_influxdb_quick.sh` - Script Rápido

```bash
./clean_influxdb_quick.sh
```

**Características:**
- 🚀 **Limpieza inmediata**: Sin confirmación
- 🚀 **Minimalista**: Solo verificaciones esenciales
- 🚀 **Rápido**: Para desarrollo y testing

**Uso recomendado:** Desarrollo, testing, automatización

## 🎯 Qué Hacen los Scripts

Ambos scripts realizan la misma operación core:

```bash
influx delete \
    --bucket "example-bucket" \
    --start "1970-01-01T00:00:00Z" \
    --stop "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --token "example-token" \
    --org "example-org"
```

Esto elimina **TODOS** los registros del bucket `example-bucket` desde 1970 hasta ahora.

## ✅ Verificación Post-Limpieza

Después de ejecutar cualquier script, puedes verificar que el bucket está limpio:

```bash
# Verificar que no hay datos
podman exec -it metrics-stack-influxdb influx query \
  'from(bucket: "example-bucket") |> range(start: -30d) |> limit(n:1)' \
  --token example-token --org example-org

# Si está vacío, no debería mostrar nada
```

## 📋 Requisitos

- ✅ Pod `metrics-stack` ejecutándose
- ✅ Contenedor `metrics-stack-influxdb` activo
- ✅ Puerto 8086 accesible
- ✅ Permisos de ejecución en los scripts

## ⚠️ Advertencias

- **🔥 ELIMINACIÓN PERMANENTE**: Los datos eliminados NO se pueden recuperar
- **🎯 Solo afecta `example-bucket`**: Los buckets `_monitoring` y `_tasks` no se tocan
- **⏱️ Sin backup automático**: Haz backup manual si necesitas los datos

## 📊 Ejemplo de Uso

```bash
# Método 1: Con confirmación (recomendado)
./clean_influxdb.sh

# Output:
# 🗑️  Script de Limpieza InfluxDB
# =====================================
# 📋 Verificando estado del contenedor InfluxDB...
# ✅ Contenedor InfluxDB está ejecutándose
# 🔗 Verificando conectividad con InfluxDB...
# ✅ InfluxDB está respondiendo
# 📊 Contando registros actuales en bucket 'example-bucket'...
# 📈 Registros encontrados: 15
# 📋 Mediciones disponibles:
#   - asl_processing
#   - backend
# 
# ⚠️  ADVERTENCIA: Esta operación eliminará TODOS los datos del bucket 'example-bucket'
# ¿Estás seguro de que quieres continuar? (y/N): y
# 🧹 Limpiando bucket 'example-bucket'...
#   → Eliminando datos por rango de tiempo...
# 🔍 Verificando limpieza...
# 🎉 ¡Limpieza exitosa!
# ✅ Bucket 'example-bucket' está ahora completamente vacío

# Método 2: Limpieza rápida (para desarrollo)
./clean_influxdb_quick.sh

# Output:
# 🧹 Limpiando bucket 'example-bucket'...
# ✅ Limpieza completada
```

## 🔧 Personalización

Para cambiar la configuración, edita las variables en los scripts:

```bash
INFLUX_TOKEN="example-token"      # Token de autenticación
INFLUX_ORG="example-org"          # Organización
INFLUX_BUCKET="example-bucket"    # Bucket a limpiar
CONTAINER_NAME="metrics-stack-influxdb"  # Nombre del contenedor
```

## 🎉 ¡Listo para Usar!

Los scripts están listos para usar y han sido probados. El bucket `example-bucket` quedará completamente limpio después de la ejecución.
