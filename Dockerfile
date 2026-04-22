FROM python:3.12-slim

WORKDIR /app

# System deps: ffmpeg (audio conversion), curl, git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Update pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/logs /app/data /app/models /app/data/cache \ 
    && chmod 777 /app/logs \
    && chmod 777 /app/data \
    && chmod 777 /app/models \
    && chmod 777 /app/data/cache

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]