#!/bin/bash

# Script para ejecutar el servicio ASL dentro del virtual environment
# Establecer directorio de trabajo
cd /home/maqueta/Compute_Vision_ASL/backend

# Activar el virtual environment
source .venv/bin/activate

# Variables de entorno para suprimir warnings
export TF_CPP_MIN_LOG_LEVEL=3
export GLOG_minloglevel=3
export ABSL_LOGGING_VERBOSITY=3
export PYTHONWARNINGS="ignore::UserWarning:sklearn,ignore::UserWarning:google.protobuf"

# Ejecutar la aplicación
exec python3 app.py
