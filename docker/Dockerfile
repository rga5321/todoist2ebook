FROM ubuntu:latest

# Instalamos dependencias del SO
RUN apt-get update && apt-get install -y locales tzdata && \
    ln -fs /usr/share/zoneinfo/Europe/Madrid /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV TZ=Europe/Madrid
RUN apt-get install -y     wget     ca-certificates     python3     python3-pip     python3-venv     git     libegl1 libopengl0

#     && rm -rf /var/lib/apt/lists/*

# Install Calibre using the official installer script
RUN apt-get install -y libxcb-cursor0 
RUN wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin

# Creamos el usuario sin privilegios
RUN useradd -m -s /bin/bash appuser

# Nos ubicamos en el home del nuevo usuario
WORKDIR /home/appuser

# Preparamos el entrypoint
COPY entrypoint.sh /home/appuser/entrypoint.sh

RUN chown appuser:appuser /home/appuser/entrypoint.sh && chmod +x /home/appuser/entrypoint.sh

# Cambiamos a usuario appuser
USER appuser

# Clonamos el repositorio
RUN git clone https://github.com/rga5321/todoist2ebook todoist2ebook

# Creamos copias de .env y vars.py a partir de las muestras
WORKDIR /home/appuser/todoist2ebook

# Creamos un entorno virtual de Python
RUN python3 -m venv .venv

# Activamos el venv e instalamos las dependencias
RUN . .venv/bin/activate && pip3 install python-dotenv

# Script de inicio
ENTRYPOINT ["/home/appuser/entrypoint.sh"]
