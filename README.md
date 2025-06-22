# ComputeVisionRemote

Este repositorio contiene un ejemplo de sistema de ComputeVision remota dividido en dos partes:

- **backend**: servidor Python que recibe imágenes por WebSocket, detecta manos mediante [MediaPipe](https://google.github.io/mediapipe/) y devuelve las coordenadas, topología de los keypoints y la letra de ASL reconocida.
- **frontend**: Aplicación Android que captura la cámara del teléfono, envía cada fotograma al backend y dibuja los puntos recibidos desde el backend en la pantalla.

## Estructura

```
.
├── backend   # Servidor Flask + WebSocket
└── frontend  # Proyecto Android (Kotlin)
```

### Archivos principales del backend

|       Archivo      | Descripción |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`           | Punto de entrada del servidor. Expone un WebSocket en `/ws` que recibe fotogramas JPEG, ejecuta la detección de manos con MediaPipe y envía las coordenadas, topología y la letra de ASL detectada en formato JSON. |
| `hand_tracker.py`  | Utilidad para dibujar los keypoints sobre un fotograma usando las herramientas de dibujo de MediaPipe. Es opcional y sirve como código de apoyo para pruebas locales.|
| `client_test.py`   | Cliente de ejemplo que se conecta al WebSocket, envía la imagen capturada desde la cámara del PC y muestra en consola la respuesta recibida.|
| `requirements.txt` | Lista de dependencias de Python necesarias para ejecutar el servidor. |

## Requisitos

- Python 3.8 o superior para el backend
- Android Studio (o las herramientas de Android SDK) para compilar la app

## Puesta en marcha del backend

1. Crear un entorno virtual y activar:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Iniciar el servidor:
   ```bash
   python app.py
   ```
   El servidor quedar\u00e1 escuchando en `ws://0.0.0.0:5000/ws`.

Para realizar pruebas rápidas se puede usar `client_test.py`, que abre la cámara del PC y se conecta al WebSocket local.

## Ejecución del frontend

1. Abrir la carpeta `frontend` con Android Studio.
2. Conectar un dispositivo o usar un emulador.
3. Compilar e instalar la app.

La URL del WebSocket se encuentra en `MainActivity.kt` y debe apuntar a la dirección IP donde se está ejecutando el backend:

```kotlin
val uri = URI("ws://192.168.1.25:5000/ws")
```

Asegurarse de que ambos dispositivos están en la misma red para que la conexión sea posible.

## Licencia

Este proyecto se proporciona como ejemplo educativo y puede reutilizarse libremente según las necesidades del usuario.
