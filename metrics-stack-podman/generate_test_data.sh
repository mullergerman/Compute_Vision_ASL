#!/bin/bash

# Script para generar datos de prueba continuos para el dashboard ASL

echo "🔄 Generando datos de prueba para el dashboard ASL..."
echo "   Presiona Ctrl+C para detener"
echo ""

# Función para generar datos ASL realistas
generate_asl_data() {
    local asl_time=$(python3 -c "import random; print(f'{random.uniform(15, 45):.1f}')")
    local mp_time=$(python3 -c "import random; print(f'{random.uniform(8, 25):.1f}')")
    local has_hand=$(python3 -c "import random; print(random.choice([0, 1]))")
    local letters=("A" "B" "C" "D" "E" "F" "G" "H" "I" "J" "K" "L" "M" "N" "O" "P" "Q" "R" "S" "T" "U" "V" "W" "X" "Y" "Z" "none")
    local letter=${letters[$RANDOM % ${#letters[@]}]}
    
    if [ "$has_hand" -eq 0 ]; then
        letter="none"
    fi
    
    python3 -c "
import json
import urllib.request
import time

data = {
    'measurement': 'asl_processing',
    'ts': int(time.time() * 1000),
    'endpoint': 'ws',
    'service': 'asl-backend',
    'duration_asl_ms': $asl_time,
    'duration_mp_ms': $mp_time,
    'has_hand': $has_hand,
    'letter_detected': '$letter'
}

try:
    req = urllib.request.Request(
        'http://localhost:8088/ingest',
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req, timeout=1)
    print(f'✅ ASL={asl_time}ms, MP={mp_time}ms, Hand={has_hand}, Letter={letter}')
except Exception as e:
    print(f'❌ Error: {e}')
"
}

# Generar datos continuamente
counter=1
while true; do
    echo -n "[$counter] "
    generate_asl_data
    ((counter++))
    
    # Pausa variable para simular carga real
    sleep_time=$(python3 -c "import random; print(f'{random.uniform(1, 3):.1f}')")
    sleep $sleep_time
done
