#!/bin/bash
# setup_and_run.sh - Setup automatico ambiente virtuale e esecuzione script SSH

set -e  # Esce se c'è un errore

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/ssh_env"
PYTHON_SCRIPT="$SCRIPT_DIR/ssh_script.py"

echo "🚀 SSH Command Executor - Setup Automatico"
echo "==========================================="

# Verifica se Python 3 è disponibile
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 non trovato. Installa con: brew install python"
    exit 1
fi

echo "✓ Python 3 trovato: $(python3 --version)"

# Crea virtual environment se non esiste
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creazione virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment creato in: $VENV_DIR"
else
    echo "✓ Virtual environment già esistente"
fi

# Attiva virtual environment
echo "🔧 Attivazione virtual environment..."
source "$VENV_DIR/bin/activate"

# Aggiorna pip e installa paramiko
echo "📚 Installazione dipendenze..."
pip install --upgrade pip
pip install paramiko

echo "✓ Paramiko installato con successo"

# Verifica se lo script Python esiste
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Script Python non trovato: $PYTHON_SCRIPT"
    echo "Assicurati che il file ssh_script.py sia nella stessa cartella"
    exit 1
fi

echo ""
echo "🎯 Esecuzione script SSH..."
echo "=========================="

# Esegui lo script Python
python "$PYTHON_SCRIPT"

echo ""
echo "✨ Fatto! Per eseguzioni future:"
echo "   1. source ssh_env/bin/activate"
echo "   2. python ssh_script.py"
echo "   OPPURE rilancia questo script: ./setup_and_run.sh"
