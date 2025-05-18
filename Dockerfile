FROM ubuntu:22.04

# Установить Python, pip, libtorrent и необходимые зависимости
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-libtorrent && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем всё содержимое проекта (скрипт, .env, торрент-файлы)
COPY . /app

# Установить python-dotenv через pip
RUN python3 -m pip install --no-cache-dir python-dotenv

VOLUME ["/app/downloads"]

ENTRYPOINT ["python3", "torentino.py"]
