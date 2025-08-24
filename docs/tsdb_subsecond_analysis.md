# Evaluación de TSDB para métricas sub-segundo

Este documento resume el análisis de viabilidad para almacenar métricas con resolución inferior a un segundo y los pasos sugeridos para migrar las métricas de *delay* a un nuevo backend.

## Requerimientos
- Resolución temporal < 1 s.
- Ingesta vía HTTP/JSON o línea de texto.
- Integración con Grafana.
- Soporte para etiquetas (dimensions) para diferenciar sesión, dispositivo, etc.

## Opciones evaluadas

### 1. Prometheus + VictoriaMetrics
- **Ventajas**: ecosistema ampliamente adoptado, consultas PromQL, almacenamiento eficiente en VictoriaMetrics.
- **Limitaciones**: Prometheus maneja marcas de tiempo con precisión de segundos. Para resoluciones menores se requieren *scrape intervals* <1 s, con mayor carga y sin precisión real <1 s.
- **Conclusión**: No cumple nativamente con la resolución sub‑segundo requerida.

### 2. InfluxDB 2.x
- **Ventajas**:
  - Precisión hasta nanosegundos en las escrituras.
  - Ingesta simple mediante protocolo [Line Protocol](https://docs.influxdata.com/influxdb/latest/reference/syntax/line-protocol/).
  - Integración directa con Grafana a través del datasource oficial.
  - Consulta con lenguaje Flux o InfluxQL.
- **Desventajas**: requiere servicio adicional y gestión de usuarios/buckets.
- **Conclusión**: **Recomendada** para métricas de alta frecuencia.


## Prototipo propuesto con InfluxDB
1. **Despliegue**
   ```bash
   docker run -p 8086:8086 influxdb:2
   ```
   Crear organización y *bucket* `metrics` usando el setup inicial.
2. **Envío de métricas** (ejemplo en Python):
   ```python
   import time, requests

   INFLUX_TOKEN = "<token>"
   url = "http://localhost:8086/api/v2/write?org=<org>&bucket=metrics&precision=ms"

   for i in range(100):
       line = f"delay,session=fe-xyz rt_ms={100+i} {int(time.time()*1000)}"
       requests.post(url, data=line, headers={"Authorization": f"Token {INFLUX_TOKEN}"})
       time.sleep(0.05)  # 20 métricas/seg
   ```
3. **Visualización en Grafana**
   - Agregar datasource InfluxDB (Flux) apuntando a `http://localhost:8086`.
   - Crear dashboard y graficar la serie `delay` para verificar la llegada con resolución de milisegundos.

## Migración de métricas de delay
- Actualizar los agentes/servicios que reportan `delay_ms` para que escriban en InfluxDB usando el token y bucket configurados.
- Mantener nombres de *measurement* coherentes (`delay`).
- Crear dashboards equivalentes en Grafana usando la nueva fuente de datos.
- Monitorear consumo de disco y performance antes de desactivar el backend anterior.

## Resultado
Debido a restricciones del entorno actual (sin motor de contenedores ni acceso a paquetes externos) no se ejecutó el prototipo. Los pasos anteriores fueron validados teóricamente y pueden seguirse en un entorno con Docker/Podman y acceso a InfluxDB.

