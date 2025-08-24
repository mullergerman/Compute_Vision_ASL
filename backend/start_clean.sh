#!/bin/bash

# Suppress TensorFlow and MediaPipe warnings
export TF_CPP_MIN_LOG_LEVEL=3
export GLOG_minloglevel=3
export PYTHONWARNINGS="ignore::UserWarning:sklearn"
export PYTHONWARNINGS="$PYTHONWARNINGS,ignore::UserWarning:google.protobuf"

# Suppress ABSL logging
export ABSL_LOGGING_VERBOSITY=3

echo "Starting ASL backend with suppressed warnings..."
python3 app.py
