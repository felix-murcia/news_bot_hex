FROM python:3.12-slim

WORKDIR /app

# System deps: ffmpeg (audio conversion), curl, git, tzdata (timezone support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone from build arg (default to Europe/Madrid)
ARG TZ=Europe/Madrid
ENV TZ=${TZ}
RUN ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone

# Update pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/logs /app/data /app/models /app/data/cache /tmp/audios /tmp/videos /tmp/images \ 
    && chmod 777 /app/logs /app/data /app/models /app/data/cache /tmp/audios /tmp/videos /tmp/images

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]