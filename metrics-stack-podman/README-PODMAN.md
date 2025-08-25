# Metrics Stack para **Podman** (InfluxDB + Grafana + Telegraf + Nginx TLS)

Este paquete usa **podman play kube** para desplegar un **Pod** con 4 contenedores.

## 1) Requisitos
- Podman (rootless recomendado) — Debian/Fedora/…
- Certificados TLS en `nginx/certs/server.crt` y `server.key` (podés usar `mkcert`).
- SELinux habilitado? Ver sección **SELinux**.

## 2) Puertos publicados (host)
- Grafana: **3000/tcp**
- InfluxDB: **8086/tcp**
- Ingesta TLS (Nginx → Telegraf): **8443/tcp**

## 3) Arranque
```bash
# Dentro del directorio del proyecto
# 1) Reemplazá el token en nginx/nginx.conf (CHANGE_ME_SUPER_TOKEN)
sed -i 's/CHANGE_ME_SUPER_TOKEN/pon_un_secreto_fuerte/g' nginx/nginx.conf

# 2) (Opcional) Generá certificados dev con mkcert
# mkcert -install
# mkcert -key-file nginx/certs/server.key -cert-file nginx/certs/server.crt localhost

# 3) Levantar el pod
podman play kube metrics-pod.yml

# Ver estado
podman ps --filter name=metrics-stack

# Logs (ejemplo)
podman logs -f metrics-stack-nginx
```

## 4) Parada / limpieza
```bash
podman play kube --down metrics-pod.yml
```

## 5) Endpoints
- Grafana: https://localhost:3000 (user: `admin`, pass: `admin` — cambiá en el YAML si querés)
- InfluxDB: http://localhost:8086 (token `example-token`, org `example-org`)
- Ingesta: `https://<tu-host>/ingest`  (valida **Bearer token**)
- Health: `https://<tu-host>/ping`

## 6) Prueba rápida
```bash
TOKEN="pon_un_secreto_fuerte"
HOST="localhost"

curl -k https://$HOST/ping

curl -k -X POST "https://$HOST/ingest"   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   --data-binary '{"measurement":"delay_ms","rt_ms":150.2,"ts":'$(($(date +%s%3N)))',"session":"fe-xyz","fe":"edge-01","device":"demo","net":"lte","country":"AR","app_ver":"1.0.0","build":"1"}'
```

## 7) Android (OkHttp) — mini ejemplo
```kotlin
val base = "https://<tu-host>"
val token = "pon_un_secreto_fuerte"

// 1) Medir RTT al /ping
val t0 = System.nanoTime()
okHttp.newCall(
  Request.Builder()
    .url("$base/ping")
    .header("Authorization", "Bearer $token")
    .build()
).execute().close()
val rttMs = (System.nanoTime() - t0) / 1e6

// 2) Enviar JSON a /ingest
val json = """
{"measurement":"delay_ms","rt_ms":$rttMs,"ts":${System.currentTimeMillis()},"session":"fe-123","fe":"edge-01","device":"SM-A236B","net":"lte"}
""".trimIndent()

okHttp.newCall(
  Request.Builder()
    .url("$base/ingest")
    .header("Authorization", "Bearer $token")
    .post(json.toRequestBody("application/json".toMediaType()))
    .build()
).execute().close()
```

## 8) InfluxDB — ejemplo de configuración
Escribir un punto usando la API HTTP:
```bash
curl -XPOST "http://localhost:8086/api/v2/write?org=example-org&bucket=example-bucket&precision=ms" \
  -H "Authorization: Token example-token" \
  --data-raw "demo,host=test value=1i"
```

Configurar Telegraf para enviar a InfluxDB:
```toml
[[outputs.influxdb_v2]]
  urls = ["http://127.0.0.1:8086"]
  token = "example-token"
  organization = "example-org"
  bucket = "example-bucket"
```

### Métricas del backend
El archivo `telegraf/backend-metrics.conf` expone un `[[inputs.http_listener_v2]]` en el puerto **8090** para recibir métricas del backend.
El agente usa `flush_interval = "1s"` y un `metric_buffer_limit = 50000` para tolerar ráfagas de tráfico.
Luego de modificar esta configuración recargá Telegraf:

```bash
sudo systemctl reload telegraf
```

## 9) SELinux (Fedora/RHEL)
Si tenés SELinux en *enforcing*, etiquetá las carpetas montadas para que los contenedores puedan acceder:
```bash
sudo chcon -Rt container_file_t $(pwd)/influxdb $(pwd)/grafana $(pwd)/telegraf $(pwd)/nginx
```
> Alternativa: usar volúmenes gestionados por Podman (`podman volume create ...`) y referenciarlos con hostPath; o deshabilitar SELinux (no recomendado).

## 10) Persistencia
- **InfluxDB** persiste en `influxdb/data`.
- **Grafana** persiste dashboards en `/var/lib/grafana/dashboards` (más configuración en provisioning).

## 11) Notas
- Telegraf habla con InfluxDB y Nginx por **localhost** porque el pod comparte netns.
- Grafana datasource apunta a `http://127.0.0.1:8086` (InfluxDB publicado al host). Si movés puertos, ajustalo en `grafana/provisioning/datasources/influxdb.yml` y reiniciá el pod.
- Para autoinicio systemd (usuario): `podman generate systemd --new --name metrics-stack` después de levantar el pod una vez.
