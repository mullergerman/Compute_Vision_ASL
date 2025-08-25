# 🤟 ASL Performance Dashboard

Dashboard de Grafana para monitorear el rendimiento del procesamiento ASL (American Sign Language) en tiempo real.

## 📊 Paneles Incluidos

### 1. 🚀 **ASL & MediaPipe Processing Times**
- **Tipo**: Time Series (líneas)
- **Descripción**: Muestra la evolución temporal de los tiempos de procesamiento
- **Métricas**:
  - `duration_asl_ms` - Tiempo de predicción ASL (azul)
  - `duration_mp_ms` - Tiempo de procesamiento MediaPipe (verde)
- **Agregación**: Promedio cada 30 segundos
- **Actualización**: Cada 5 segundos

### 2. 📊 **Average Processing Time Distribution**
- **Tipo**: Pie Chart
- **Descripción**: Distribución porcentual de tiempos promedio
- **Métricas**: Promedio de ASL vs MediaPipe
- **Útil para**: Ver qué componente consume más tiempo

### 3. 📈 **Key Performance Indicators**
- **Tipo**: Stat (métricas grandes)
- **Métricas mostradas**:
  - **ASL Processing (ms)**: Tiempo promedio ASL (azul)
  - **MediaPipe Processing (ms)**: Tiempo promedio MediaPipe (verde)
  - **Total Requests**: Número total de requests (morado)
  - **Hand Detection Rate (%)**: Porcentaje de detección de manos (naranja)

### 4. 📊 **Processing Time Distribution**
- **Tipo**: Histogram
- **Descripción**: Distribución de frecuencias de tiempos de procesamiento
- **Buckets**: 5ms de ancho
- **Útil para**: Identificar patrones de rendimiento

### 5. 🔤 **ASL Letters Detected**
- **Tipo**: Donut Chart
- **Descripción**: Frecuencia de letras ASL detectadas
- **Útil para**: Ver qué letras se detectan más frecuentemente

## 🎯 Configuración

### Datasource
- **Nombre**: InfluxDB
- **URL**: http://127.0.0.1:8086
- **Organización**: example-org
- **Bucket**: example-bucket
- **Token**: example-token

### Tiempo por Defecto
- **Rango**: Últimos 5 minutos
- **Refresh**: Cada 5 segundos
- **Timezone**: Browser

## 🚀 Acceso al Dashboard

### URL Direct
```
http://localhost:3000/d/asl-performance
```

### Credenciales Grafana
- **Usuario**: admin
- **Contraseña**: admin

## 📋 Queries InfluxDB (Flux)

### Tiempo de Procesamiento ASL
```flux
from(bucket: "example-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "asl_processing" and r._field == "duration_asl_ms")
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
```

### Tiempo de Procesamiento MediaPipe
```flux
from(bucket: "example-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "asl_processing" and r._field == "duration_mp_ms")
  |> aggregateWindow(every: 30s, fn: mean, createEmpty: false)
```

### Tasa de Detección de Manos
```flux
from(bucket: "example-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "asl_processing" and r._field == "has_hand")
  |> mean()
  |> map(fn: (r) => ({ r with _value: r._value * 100.0 }))
```

## 🧪 Generar Datos de Prueba

Para poblar el dashboard con datos de prueba:

```bash
# Generar datos continuos (Ctrl+C para parar)
./generate_test_data.sh

# O generar un lote rápido
python3 -c "
import json, urllib.request, time, random
for i in range(20):
    data = {
        'measurement': 'asl_processing',
        'ts': int(time.time() * 1000),
        'endpoint': 'ws',
        'service': 'asl-backend', 
        'duration_asl_ms': random.uniform(15, 45),
        'duration_mp_ms': random.uniform(8, 25),
        'has_hand': random.choice([0, 1]),
        'letter_detected': random.choice(['A','B','C','D','E','none'])
    }
    req = urllib.request.Request('http://localhost:8088/ingest', 
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=1)
    print(f'Data {i+1} sent')
    time.sleep(0.1)
"
```

## 🎨 Personalización

### Colores
- **ASL Processing**: Azul (#3274D9)
- **MediaPipe**: Verde (#73BF69)
- **Total Requests**: Morado (#8F3BB8)
- **Hand Detection**: Naranja (#FF9830)

### Umbrales
- **Verde**: < 80ms (rendimiento óptimo)
- **Rojo**: > 80ms (rendimiento degradado)

## 📈 Interpretación de Métricas

### Tiempos Esperados
- **ASL Processing**: 15-45ms (normal)
- **MediaPipe**: 8-25ms (normal)
- **Total**: 25-70ms por frame

### Tasa de Detección
- **> 80%**: Excelente detección
- **60-80%**: Buena detección
- **< 60%**: Revisar calidad de entrada

## 🔧 Troubleshooting

### Dashboard vacío
```bash
# Verificar datos en InfluxDB
podman exec -it metrics-stack-influxdb influx query \
  'from(bucket: "example-bucket") |> range(start: -5m) |> limit(n:5)' \
  --token example-token --org example-org
```

### Grafana no responde
```bash
# Reiniciar Grafana
podman restart metrics-stack-grafana

# Verificar salud
wget -q -O - http://localhost:3000/api/health
```

## 📁 Archivos

- `asl-performance.json` - Dashboard JSON
- `generate_test_data.sh` - Generador de datos de prueba
- `dashboards.yml` - Configuración de provisioning

¡El dashboard está listo para monitorear tu aplicación ASL! 🎉
