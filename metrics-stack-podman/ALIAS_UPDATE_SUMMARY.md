# ✅ Dashboard ASL - Alias Actualizados

## 🎯 **Modificación Solicitada:**
Actualizar el panel "Average Processing Time Distribution" para mostrar alias simples:
- `duration_asl_ms`
- `duration_mp_ms`

## ✅ **Cambios Aplicados:**

### 📊 **Panel Modificado:** "Average Processing Time Distribution" (ID: 2)

**ANTES:**
```flux
# Query A:
|> yield(name: "ASL Avg")

# Query B:  
|> yield(name: "MediaPipe Avg")
```

**DESPUÉS:**
```flux
# Query A:
|> yield(name: "duration_asl_ms")

# Query B:
|> yield(name: "duration_mp_ms")
```

### 🔧 **Queries Flux Actualizadas:**

#### **Query A (ASL Processing):**
```flux
from(bucket: "example-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "asl_processing" and r._field == "duration_asl_ms")
  |> mean()
  |> yield(name: "duration_asl_ms")
```

#### **Query B (MediaPipe Processing):**
```flux
from(bucket: "example-bucket")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "asl_processing" and r._field == "duration_mp_ms")
  |> mean()
  |> yield(name: "duration_mp_ms")
```

## 📊 **Resultado Visual:**

En el **Pie Chart** "Average Processing Time Distribution" ahora se mostrará:
- **`duration_asl_ms`** (en lugar de "ASL Avg")
- **`duration_mp_ms`** (en lugar de "MediaPipe Avg")

## 🎯 **Equivalencia con Graphite:**

En Graphite usarías:
```
alias(sumSeries(stats.timers.asl.processing.mean), "duration_asl_ms")
alias(sumSeries(stats.timers.mp.processing.mean), "duration_mp_ms")  
```

En InfluxDB/Flux usamos:
```flux
|> yield(name: "duration_asl_ms")
|> yield(name: "duration_mp_ms")
```

## ✅ **Verificación:**

- ✅ Archivo respaldado: `asl-performance.json.backup`
- ✅ Dashboard actualizado: `asl-performance.json`
- ✅ Queries modificadas correctamente
- ✅ 6 datos de prueba enviados para verificar

## 🚀 **Para Ver los Cambios:**

1. Ir a: http://localhost:3000/d/asl-performance
2. Buscar el panel "📊 Average Processing Time Distribution"
3. Los labels del pie chart ahora mostrarán:
   - `duration_asl_ms`
   - `duration_mp_ms`

## 📋 **Otros Paneles (Sin Cambios):**

Los demás paneles mantienen sus nombres descriptivos:
- Panel 1: "ASL Processing Time" / "MediaPipe Processing Time"
- Panel 3: "ASL Processing (ms)" / "MediaPipe Processing (ms)" / etc.
- Panel 4: "ASL Processing" / "MediaPipe Processing"
- Panel 5: Sin cambios (letras detectadas)

## 🎉 **Modificación Completada!**

El panel "Average Processing Time Distribution" ahora muestra exactamente los alias solicitados: `duration_asl_ms` y `duration_mp_ms`.
