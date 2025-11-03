# Detección de Postura con MediaPipe y Streamlit

Este proyecto implementa un sistema de detección de postura en tiempo real (de pie o sentado) utilizando MediaPipe, OpenCV y una interfaz visual desarrollada en Streamlit.
El sistema fue implementado dentro de un contenedor Docker, garantizando portabilidad y aislamiento del entorno de ejecución.

## 1. Preparar el entorno de Python en Ubuntu
Para mantener el proyecto ordenado y que no se mezclen las librerías del sistema con las del proyecto, se creó un entorno virtual de Python.
Instala Python + herramientas básicas


### 1.1 Crear carpeta del proyecto
```
mkdir quiz_pose
cd quiz_pose
```
### 1.2 Se creo un entorno virtual


```
python3 -m venv .venv
source .venv/bin/activate
```
Luego de esto se instalaron las librerias necesarias, en este caso se instalo mediapipe que es la librería de Google que detecta la pose del cuerpo y nos da los landmarks (cadera, rodilla, hombro, etc.). Tambien se instalo opencv-python (cv2) que permite leer la cámara, cargar imágenes y dibujar encima de ellas (líneas, texto, puntos)y por ultimos se intalo streamlit que  sirve para crear una interfaz web rápida donde se muestra el resultado de la detección.

```
pip install mediapipe opencv-python streamlit
```

## 2. Captura de cámara y procesamiento con hilos 

En este paso pasamos de trabajar en tiempo real con la cámara.  
Para que el programa no se trabe y pueda hacer varias cosas al mismo tiempo, usamos hilos (threads) y sincronización.

La idea fue separar el trabajo en dos hilos principales:

1. **Hilo 1 → Captura de cámara**  
   Solo se encarga de leer la cámara y guardar el último frame.
2. **Hilo 2 → Procesamiento**  
   Espera a que haya un frame nuevo, lo manda a MediaPipe, clasifica si está “De pie” o “Sentado” y lo muestra.

Además se usaron:
- **mutex** para proteger las variables compartidas.
- **Semaforo** para avisar que hay un frame nuevo y que el hilo de procesamiento puede trabajar.

---

### 2.1 Variables compartidas

En el código definimos estas variables globales:frame_compartido y postura_actual son variables compartidas ya que las usan varios hilos. Por eso usamos lock para que no las editen al mismo tiempo y sem_frame empieza en 0 porque al inicio no hay ningún frame listo.

```

frame_compartido = None        # aquí se guarda el último frame que leyó la cámara
postura_actual = "desconocida" # aquí se guarda el último resultado ("De pie", "Sentado")
lock = threading.Lock()        # mutex para proteger las variables compartidas
sem_frame = threading.Semaphore(0)  # semáforo para avisar que hay un frame listo
```
### 2.2 Hilo 1: leer la cámara

Lo que hace este hilo es abre la cámara (VideoCapture(0)). Entra en un while True para leer video continuamente y cada vez que obtiene un frame bueno entra al with lock: → esto es la sección crítica. Ahí guarda el frame en frame_compartido. Luego llama a sem_frame.release() → esto suelta el semáforo y significa “ya hay un frame listo para procesar”. y por ultimo el time.sleep(0.01) es solo para no saturar la CPU.


```
def hilo_camara():
    global frame_compartido
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # zona crítica
        with lock:
            frame_compartido = frame

        # avisar al otro hilo que ya hay un frame
        sem_frame.release()

        time.sleep(0.01)
```

### 2.3 Hilo 2: procesar con MediaPipe

En este hilo se utilizo sem_frame.acquire() por que  aquí se queda esperando hasta que el hilo de la cámara diga “ya hay un frame”. Esto evita que el hilo de procesamiento esté preguntando todo el tiempo si ya hay frame. Cuando hay un frame, lo copia dentro de un with lock para que no se modifique mientras lo estamos leyendo. Convierte el frame a RGB y lo pasa a MediaPipe. Si MediaPipe encontró el cuerpo, llama a clasificar_postura(...) y obtiene “De pie” o “Sentado”. Guarda el resultado en postura_actual dentro de un with lock: (otra vez, para no dañar los datos). Dibuja los puntos y la etiqueta en la imagen y 
la muestra.

```
def hilo_procesamiento():
    global frame_compartido, postura_actual

    while True:
        # 1. esperar a que la cámara deje un frame
        sem_frame.acquire()

        # 2. copiar el frame de forma segura
        with lock:
            frame_local = frame_compartido.copy() if frame_compartido is not None else None

        if frame_local is None:
            continue

        # 3. procesar con mediapipe
        rgb = cv2.cvtColor(frame_local, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if results.pose_landmarks:
            postura = clasificar_postura(results.pose_landmarks.landmark)
        else:
            postura = "No detectada"

        # 4. guardar el resultado de forma segura
        with lock:
            postura_actual = postura

        # 5. dibujar para ver que sí funciona
        mp.solutions.drawing_utils.draw_landmarks(
            frame_local, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
        )
        cv2.putText(frame_local, postura, (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

        cv2.imshow("Pose realtime", frame_local)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    cv2.destroyAllWindows()

```

### 2.4 Por qué usamos semáforo y mutex

En esta practica se utilizo mutex ya que protege los datos y lo usamos cuando vamos a leer o escribir algo en frame_compartido o postura_actual. Tambien se utiliza semafora para controlar el flujo y  sirve para que el hilo de porcesamiento no pocese cuando este vacio sino solo cuando la camara ya dejo algo.

### 2.5 Lanzar los hilos

Al final del archivo se crean y se arrancan los hilos, daemon=True hace que los hilos se apaguen cuando se cierre el programa y el while True del final es solo para que el programa principal no termine mientras los hilos trabajan.

```
if __name__ == "__main__":
    t_cam = threading.Thread(target=hilo_camara, daemon=True)
    t_proc = threading.Thread(target=hilo_procesamiento, daemon=True)

    t_cam.start()
    t_proc.start()

    # mantener vivo el hilo principal
    while True:
        time.sleep(1)

```

## 3. Interfaz gráfica con Streamlit

Una vez que ya teníamos funcionando la detección de postura en tiempo real con hilos, el siguiente paso fue crear una interfaz visual para el usuario.  
Para eso se utilizó Streamlit, que permite convertir programas de Python en aplicaciones web de manera muy sencilla.

---

### 3.1 Objetivo de la interfaz

El propósito de esta parte fue mostrar de forma amigable y en tiempo real la cámara junto con la postura detectada. El usuario solo necesita abrir el navegador, ver el video en vivo y el texto que indica si está **“🧍 De pie”** o **“🪑 Sentado”**.

---

### 3.2 Estructura del archivo `app_streamlit.py`

El archivo principal de la interfaz (`app_streamlit.py`) se dividió en tres secciones:

1. **Configuración de la página e importaciones**
2. **Captura y procesamiento de video**
3. **Interfaz y botones de control**

---

### 3.3 Configuración de la página

Primero se configuró el título y el diseño de la aplicación:

```
import streamlit as st
import cv2
import mediapipe as mp
import threading
import time

st.set_page_config(page_title="Detección de Postura", layout="wide")
st.title("🧠 Detección de Postura en Tiempo Real")
```


### 3.4 Zona de visualización
Como Streamlit no tiene acceso directo a la cámara, así que se usó OpenCV para capturar cada cuadro y luego mostrarlo como una imagen en la app.
Para eso se utilizó st.image(), que se actualiza constantemente dentro de un bucle.

```
frame_window = st.image([])  

```
Cada vez que se procesa un nuevo frame, se actualiza este componente:

```
frame_window.image(frame_rgb, channels="RGB")

```
### 3.5 Botones y control del flujo

Streamlit no maneja loops tradicionales de manera interactiva, por eso se usaron botones con banderas para controlar cuándo se inicia o se detiene la cámara, el botón Detener se le dio una clave (key) única para evitar el error de IDs duplicados que aparecía al inicio. Cuando el usuario presiona Iniciar, se crea el hilo de procesamiento y se comienza a mostrar la cámara.
Cuando presiona “Detener”, se libera la cámara y se cierra la ventana.

```
start = st.button("Iniciar detección")
stop = st.button("Detener", key="stop_button")

```
### 3.6 Detección dentro de Streamlit

Dentro del ciclo de Streamlit se integró el mismo modelo de MediaPipe utilizado antes si se detecta una persona, se dibujan los landmarks y se calcula la postura con la función clasificar_postura().

El resultado se muestra debajo del video en tiempo real:


```
mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

results = pose.process(frame_rgb)
st.markdown(f"### Postura detectada: **{postura}**")
```

## 4. Contenedor Docker para ejecutar toda la aplicación

Finalmente, se creó un contenedor con Docker para que toda la aplicación se pueda ejecutar de forma aislada, sin depender del entorno del computador.  
Esto permite que cualquier persona pueda correr el proyecto con solo tener Docker instalado, sin necesidad de instalar Python ni librerías manualmente.

---

### 4.1 Archivo `Dockerfile`

Dentro del proyecto se creó un archivo llamado Dockerfile, que define la imagen paso a paso:

```
# Imagen base de Python
FROM python:3.10-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiar todos los archivos del proyecto al contenedor
COPY . /app

# Instalar dependencias necesarias para OpenCV y Streamlit
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Instalar librerías de Python necesarias
RUN pip install --no-cache-dir mediapipe opencv-python streamlit

# Comando por defecto: ejecutar la aplicación de Streamlit
CMD ["streamlit", "run", "app_streamlit.py", "--server.address=0.0.0.0"]

```

### 4.2 Construir la imagen Docker

Con el archivo Dockerfile listo, se construyó la imagen ejecutando, durante la construcción, Docker instala todas las dependencias necesarias

```
docker build -t quiz_pose .
```

### 4.3 Ejecutar el contenedor

Cuando la imagen termina de construirse, se puede ejecutar con: -p 8501:8501 con esto se conecta el puerto 8501 del contenedor con el mismo puerto del host.
Streamlit usa ese puerto por defecto, así que luego se puede abrir en el navegador. Tambien se debe tener en cuenta --device=/dev/video0:/dev/video0 ya que da el acceso a la cámara del computador dentro del contenedor. Sin esto, el contenedor no puede usar la webcam. Al igual que --privileged que otorga permisos adicionales al contenedor (necesarios para usar dispositivos físicos como la cámara).
```
docker run -p 8501:8501 --device=/dev/video0:/dev/video0 --privileged quiz_pose
```

### 4.5 Abrir la aplicación en el navegador

Cuando el contenedor se está ejecutando correctamente, solo hay que abrir el navegador y entrar a:

```
http://localhost:8501
```

Ahí se mostrará la interfaz de Streamlit con la cámara y la detección de postura funcionando dentro del contenedor Docker.
