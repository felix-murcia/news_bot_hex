FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime

WORKDIR /app

# Instalar Rust para tiktoken (necesario para whisper)
RUN apt-get update && apt-get install -y git ffmpeg curl build-essential && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    rm -rf /var/lib/apt/lists/*

# Agregar Rust al PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Verificar Rust está instalado
RUN rustc --version

# Actualizar pip
RUN pip install --upgrade pip setuptools wheel

# Instalar whisper (ahora tiktoken compilará con Rust)
RUN pip install --no-cache-dir openai-whisper

# Instalar llama-cpp-python
RUN pip install llama-cpp-python==0.2.60

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs data models

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]