FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    mv /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ && \
    mv /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ && \
    rm -rf /tmp/ffmpeg*

RUN pip install --upgrade pip setuptools wheel

# Instalar whisper
RUN pip install git+https://github.com/openai/whisper.git

# Instalar faster-whisper (el que usa tu transcriber)
RUN pip install faster-whisper

# Instalar llama-cpp-python
RUN pip install llama-cpp-python==0.2.60 --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Arreglar libstdc++
RUN rm -f /opt/conda/lib/libstdc++.so* && \
    ln -s /usr/lib/x86_64-linux-gnu/libstdc++.so.6 /opt/conda/lib/libstdc++.so.6

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs data models

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]