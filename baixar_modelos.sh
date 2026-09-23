#!/bin/sh
# Baixa os modelos de voz do Kokoro (cerca de 350 MB) para a pasta modelos/
# e confere a integridade de cada arquivo pelo SHA-256.
# Origem: releases oficiais do kokoro-onnx (https://github.com/thewh1teagle/kokoro-onnx).
set -e
cd "$(dirname "$0")"
mkdir -p modelos
BASE=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0

baixar() {
    arquivo=$1; hash=$2
    if [ -f "modelos/$arquivo" ] && echo "$hash  modelos/$arquivo" | shasum -a 256 -c - >/dev/null 2>&1; then
        echo "ok, já existe: $arquivo"
        return
    fi
    echo "baixando $arquivo ..."
    curl -L --fail --progress-bar -o "modelos/$arquivo" "$BASE/$arquivo"
    echo "$hash  modelos/$arquivo" | shasum -a 256 -c -
}

baixar kokoro-v1.0.onnx 7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5
baixar voices-v1.0.bin  bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d
echo "modelos prontos em $(pwd)/modelos"
