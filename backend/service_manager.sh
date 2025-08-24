#!/bin/bash

# Script para gestionar el servicio ASL Backend

SERVICE_NAME="asl-backend.service"

case "$1" in
    start)
        echo "Iniciando servicio ASL Backend..."
        sudo systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "Deteniendo servicio ASL Backend..."
        sudo systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "Reiniciando servicio ASL Backend..."
        sudo systemctl restart $SERVICE_NAME
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        echo "Mostrando logs del servicio (presiona 'q' para salir)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    enable)
        echo "Habilitando servicio para inicio automático..."
        sudo systemctl enable $SERVICE_NAME
        ;;
    disable)
        echo "Deshabilitando servicio de inicio automático..."
        sudo systemctl disable $SERVICE_NAME
        ;;
    reload)
        echo "Recargando configuración de systemd..."
        sudo systemctl daemon-reload
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs|enable|disable|reload}"
        echo ""
        echo "Comandos disponibles:"
        echo "  start    - Iniciar el servicio"
        echo "  stop     - Detener el servicio"
        echo "  restart  - Reiniciar el servicio"
        echo "  status   - Ver estado del servicio"
        echo "  logs     - Ver logs en tiempo real"
        echo "  enable   - Habilitar inicio automático"
        echo "  disable  - Deshabilitar inicio automático"
        echo "  reload   - Recargar configuración"
        exit 1
        ;;
esac

exit 0
