#! /bin/bash

# Cargar las variables de entorno de env.local
# set -a
# source /home/appuser/env.local
# set +a

# Sobrescribir .env con env.local
cp /home/appuser/env.local /home/appuser/todoist2ebook/.env
cp /home/appuser/env.local /home/appuser/vars.py

# Generar vars.py a partir de env.local
# Suponiendo que env.local tiene VAR1=valor1
# el script transformará eso a:
# VAR1 = "valor1"

# > /home/appuser/todoist2ebook/vars.py
# while IFS='=' read -r key value; do
#     echo "$key = \"$value\"" >> /home/appuser/todoist2ebook/vars.py
# done < /home/appuser/env.local

# Finalmente ejecutar main.py
cd /home/appuser/todoist2ebook
/home/appuser/todoist2ebook/.venv/bin/python3 main.py