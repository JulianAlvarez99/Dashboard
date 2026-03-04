#!/usr/bin/env bash

# Script de configuración para el entorno de producción

echo "========================================="
echo "   Configuración de Entorno de Producción"
echo "========================================="

# Salir si ocurre un error
set -e

# Asegurar que estamos en el directorio raíz del proyecto
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "[*] Comprobando Python..."
if ! command -v python3 &> /dev/null
then
    echo "Python3 no está instalado. Instálelo primero."
    exit 1
fi

echo "[*] Configurando Entorno Virtual (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "[OK] Entorno virtual creado."
else
    echo "[OK] Entorno virtual ya existe."
fi

# Activar entorno virtual (sintaxis bash)
source .venv/bin/activate

echo "[*] Instalando/Actualizando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt
echo "[OK] Dependencias instaladas."

echo "[*] Configurando variables de entorno (.env)..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[!] Archivo .env creado desde .env.example. Por favor, edítelo con las credenciales correctas."
    else
        echo "[!] No se encontró .env ni .env.example. Deberá crear el archivo .env manualmente."
    fi
else
    echo "[OK] Archivo .env ya existe."
fi

echo "[*] Configuración inicializada exitosamente."
echo ""
echo "Recuerde:"
echo " 1. Revisar y/o actualizar el archivo .env"
echo " 2. Ejecutar las migraciones de base de datos:"
echo "      alembic -x db=global upgrade head"
echo "      alembic -x db=tenant upgrade head"
echo " 3. Ejecutar 'python3 scripts/init_db.py' para configurar la base de datos si aún no lo ha hecho."
echo " 4. Utilizar un manejador de procesos como Supervisor, PM2 o Systemd para servir la aplicación en producción con Uvicorn o Gunicorn."
echo "========================================="