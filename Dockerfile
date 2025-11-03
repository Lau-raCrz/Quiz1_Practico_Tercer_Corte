# Imagen base de Python
FROM python:3.10-slim

# Directorio de trabajo
WORKDIR /app

# Copiar los archivos del proyecto
COPY . /app

# Instalar dependencias del sistema necesarias para OpenCV y MediaPipe
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Actualizar pip y setuptools
RUN pip install --upgrade pip setuptools wheel

# Instalar dependencias con más tiempo de espera
RUN pip install --no-cache-dir --default-timeout=200 opencv-python streamlit

# MediaPipe a veces se demora, así que la instalamos aparte con reintento
RUN pip install --no-cache-dir --default-timeout=300 mediapipe || \
    (echo "⚠️ Primer intento falló, reintentando..." && sleep 10 && pip install --no-cache-dir --default-timeout=300 mediapipe)

# Exponer el puerto del servidor Streamlit
EXPOSE 8501

# Comando para ejecutar Streamlit
CMD ["streamlit", "run", "app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
