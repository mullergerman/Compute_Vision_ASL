#!/usr/bin/env python3
import socket
import time
import os

# Configuración de Graphite
GRAPHITE_HOST = os.getenv("GRAPHITE_HOST", "localhost")
GRAPHITE_PORT = int(os.getenv("GRAPHITE_PORT", "2003"))

print(f"Graphite server: {GRAPHITE_HOST}:{GRAPHITE_PORT}")

def send_metric(name: str, value: float) -> bool:
    """Send a single metric to Graphite using the plaintext protocol."""
    timestamp = int(time.time())
    message = f"{name} {value} {timestamp}\n"
    try:
        print(f"Enviando métrica: {message.strip()}")
        with socket.create_connection((GRAPHITE_HOST, GRAPHITE_PORT), timeout=5) as sock_conn:
            sock_conn.sendall(message.encode("utf-8"))
        print("✓ Métrica enviada exitosamente")
        return True
    except OSError as exc:
        print(f"✗ Error enviando métrica {name}: {exc}")
        return False

if __name__ == "__main__":
    # Enviar algunas métricas de prueba
    print("Enviando métricas de prueba a Graphite...")
    
    send_metric("test.counter", 1.0)
    send_metric("test.temperature", 23.5)
    send_metric("asl.predictions.test", 100)
    
    print("\nPrueba completada. Revisa Grafana en: http://localhost:3000")
