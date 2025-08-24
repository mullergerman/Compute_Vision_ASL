# Servicio ASL Backend

## Descripción
El servicio ASL Backend se ejecuta automáticamente como un servicio de sistema usando systemd. Esto garantiza que:

- ✅ Se inicie automáticamente al arrancar el sistema
- ✅ Se reinicie automáticamente si ocurre un error
- ✅ Se ejecute siempre dentro del virtual environment de Python
- ✅ Los warnings estén suprimidos para una salida limpia
- ✅ Los logs sean gestionados por systemd

## Archivos del Servicio

### 1. `/etc/systemd/system/asl-backend.service`
Archivo de configuración del servicio systemd

### 2. `/home/maqueta/Compute_Vision_ASL/backend/asl_service.sh`
Script de inicio que activa el virtual environment y ejecuta la aplicación

### 3. `/home/maqueta/Compute_Vision_ASL/backend/service_manager.sh`
Script de gestión del servicio con comandos útiles

## Comandos de Gestión

### Usando el script de gestión:
```bash
./service_manager.sh start      # Iniciar servicio
./service_manager.sh stop       # Detener servicio
./service_manager.sh restart    # Reiniciar servicio
./service_manager.sh status     # Ver estado
./service_manager.sh logs       # Ver logs en tiempo real
./service_manager.sh enable     # Habilitar inicio automático
./service_manager.sh disable    # Deshabilitar inicio automático
```

### Usando systemctl directamente:
```bash
sudo systemctl start asl-backend.service
sudo systemctl stop asl-backend.service
sudo systemctl restart asl-backend.service
sudo systemctl status asl-backend.service
sudo systemctl enable asl-backend.service
sudo systemctl disable asl-backend.service
```

## Logs del Servicio

### Ver logs en tiempo real:
```bash
sudo journalctl -u asl-backend.service -f
```

### Ver últimos 50 logs:
```bash
sudo journalctl -u asl-backend.service -n 50
```

### Ver logs desde una fecha específica:
```bash
sudo journalctl -u asl-backend.service --since "2025-08-12 20:00:00"
```

## Configuración de Reinicio Automático

El servicio está configurado para:
- **RestartSec=10**: Esperar 10 segundos antes de reiniciar
- **StartLimitBurst=5**: Máximo 5 intentos de reinicio
- **StartLimitInterval=60**: En un período de 60 segundos

## Estado del Servicio

El servicio está actualmente:
- ✅ **Habilitado** para inicio automático
- ✅ **Activo** y ejecutándose
- ✅ **Escuchando** en puerto 5000
- ✅ **Ejecutándose** dentro del virtual environment

## Verificación del Servicio

Para verificar que el servicio está funcionando:
```bash
# Verificar estado
./service_manager.sh status

# Verificar que escucha en el puerto
ss -tlnp | grep :5000

# Verificar proceso Python
ps aux | grep python3 | grep app_fixed.py
```

## Solución de Problemas

### Si el servicio no inicia:
1. Verificar logs: `./service_manager.sh logs`
2. Verificar permisos de archivos: `ls -la asl_service.sh app_fixed.py`
3. Verificar virtual environment: `ls -la .venv/`

### Si el servicio se reinicia constantemente:
1. Ver logs detallados: `sudo journalctl -u asl-backend.service --no-pager`
2. Verificar dependencias Python: `source .venv/bin/activate && pip list`
3. Probar ejecución manual: `./asl_service.sh`

## Red y Seguridad

- **Puerto**: 5000
- **Interfaz**: 0.0.0.0 (todas las interfaces)
- **Usuario**: maqueta (no root)
- **Logs**: Gestionados por systemd journal

## Mantenimiento

### Actualizar la aplicación:
1. Detener servicio: `./service_manager.sh stop`
2. Actualizar código
3. Reiniciar servicio: `./service_manager.sh start`

### Cambiar configuración del servicio:
1. Editar: `sudo nano /etc/systemd/system/asl-backend.service`
2. Recargar: `./service_manager.sh reload`
3. Reiniciar: `./service_manager.sh restart`
