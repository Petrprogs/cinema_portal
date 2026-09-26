# Python >=3.12 обязателен: в server.py используются вложенные кавычки в f-строках (PEP 701)
FROM python:3.12-slim

# ffmpeg нужен по README (локальные/прокси-потоки), остальное — минимум для slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py utils.py VideoBalancersApi.py config.py.example db.json.example ./
COPY videobalancers/ ./videobalancers/
COPY templates/ ./templates/
COPY res/ ./res/

ENV PYTHONUNBUFFERED=1

EXPOSE 5001

# Если config.py / db.json не подмонтированы — создать из примеров, затем старт
CMD ["sh", "-c", "test -f config.py || cp config.py.example config.py; test -f db.json || cp db.json.example db.json; exec python server.py"]
