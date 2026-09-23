#!/bin/sh
# Instala o book-to-audio: ferramentas do sistema, modelos de voz, ambiente Python
# e, se o Claude Code estiver instalado, a skill /audiolivro.
# Pode rodar de novo sem problema: cada passo pula o que já está feito.
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"

echo "1/4 ferramentas do sistema (Homebrew)"
if ! command -v brew >/dev/null 2>&1; then
    echo "   Homebrew não encontrado. Instale em https://brew.sh e rode este script de novo."
    exit 1
fi
for f in ffmpeg espeak-ng uv; do
    if brew list "$f" >/dev/null 2>&1 || command -v "$f" >/dev/null 2>&1; then
        echo "   ok: $f"
    else
        echo "   instalando $f"
        brew install "$f"
    fi
done

echo "2/4 modelos de voz"
./baixar_modelos.sh

echo "3/4 ambiente Python"
uv sync

echo "4/4 skill do Claude Code"
if [ -d "$HOME/.claude" ]; then
    mkdir -p "$HOME/.claude/skills"
    DESTINO="$HOME/.claude/skills/audiolivro"
    if [ -L "$DESTINO" ] && [ "$(readlink "$DESTINO")" = "$REPO/skill" ]; then
        echo "   ok: /audiolivro já ligada"
    elif [ -e "$DESTINO" ]; then
        echo "   já existe algo em $DESTINO que não é este repositório; não mexi"
    else
        ln -s "$REPO/skill" "$DESTINO"
        echo "   ligada: /audiolivro (abra uma sessão nova do Claude Code para ela aparecer)"
    fi
else
    echo "   Claude Code não encontrado; use pela linha de comando: uv run gerar_audio.py arquivo.pdf"
fi

echo "pronto."
