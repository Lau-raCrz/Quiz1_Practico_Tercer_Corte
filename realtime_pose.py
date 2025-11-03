import cv2
import mediapipe as mp
import threading
import time
import socket  # para 5C
from math import fabs

# =============== CONFIG MEDIAPIPE ===============
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False,  # porque es video
                    model_complexity=1,
                    enable_segmentation=False,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5)

# =============== VARIABLES COMPARTIDAS ===============
frame_compartido = None        # último frame leído por la cámara
postura_actual = "desconocida" # lo que detectamos
lock = threading.Lock()        # mutex para proteger las variables
sem_frame = threading.Semaphore(0)  # semáforo: indica "hay frame nuevo"


# =============== HILO 1: CAPTURAR CÁMARA ===============
def hilo_camara():
    global frame_compartido
    cap = cv2.VideoCapture(0)  # 0 = webcam
    if not cap.isOpened():
        print("❌ No se pudo abrir la cámara")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        # guardamos el frame en la variable compartida
        with lock:  # 🔒 protegemos
            frame_compartido = frame

        # avisamos al hilo de procesamiento que hay un frame nuevo
        sem_frame.release()

        # pequeño respiro
        time.sleep(0.01)


# =============== FUNCIÓN: CLASIFICAR POSTURA ===============
def clasificar_postura(landmarks):
    # usamos mismos índices que en el paso 4
    left_hip = landmarks[23]
    right_hip = landmarks[24]
    left_knee = landmarks[25]
    right_knee = landmarks[26]

    hip_y = (left_hip.y + right_hip.y) / 2
    knee_y = (left_knee.y + right_knee.y) / 2

    diff = knee_y - hip_y

    # umbral ajustable
    if diff < 0.15:
        return "Sentado"
    else:
        return "De pie"


# =============== HILO 2: PROCESAR POSE ===============
def hilo_procesamiento():
    global frame_compartido, postura_actual

    while True:
        # esperar a que la cámara ponga un frame
        sem_frame.acquire()

        # tomar el frame de forma segura
        with lock:
            frame_local = frame_compartido.copy() if frame_compartido is not None else None

        if frame_local is None:
            continue

        # convertir a RGB para mediapipe
        rgb = cv2.cvtColor(frame_local, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)

        if results.pose_landmarks:
            postura = clasificar_postura(results.pose_landmarks.landmark)
        else:
            postura = "No detectada"

        # actualizar la variable compartida de postura
        with lock:
            postura_actual = postura

        # dibujar y mostrar (solo para debug rápido)
        mp.solutions.drawing_utils.draw_landmarks(
            frame_local,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS
        )
        cv2.putText(frame_local, postura, (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

        cv2.imshow("Pose realtime", frame_local)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    cv2.destroyAllWindows()


# =============== HILO 3 (5C): ENVIAR POSTURA POR SOCKET ===============
def hilo_socket():
    """
    Hilo opcional: abre un servidor TCP en el puerto 5000
    y cada cierto tiempo envía la postura actual al cliente que se conecte.
    Esto sirve si tu profe quiere ver que usaste sockets.
    """
    global postura_actual
    HOST = "0.0.0.0"
    PORT = 5000

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"🟢 Servidor de postura escuchando en {HOST}:{PORT}")

    conn, addr = server.accept()
    print(f"📡 Cliente conectado desde {addr}")

    try:
        while True:
            with lock:
                msg = postura_actual
            # enviamos como texto
            conn.sendall((msg + "\n").encode("utf-8"))
            time.sleep(0.5)
    except Exception as e:
        print("Error en socket:", e)
    finally:
        conn.close()
        server.close()


# =============== MAIN ===============
if __name__ == "__main__":
    # lanzar hilos
    t_cam = threading.Thread(target=hilo_camara, daemon=True)
    t_proc = threading.Thread(target=hilo_procesamiento, daemon=True)
    t_sock = threading.Thread(target=hilo_socket, daemon=True)

    t_cam.start()
    t_proc.start()
    t_sock.start()

    # mantener vivo el hilo principal
    while True:
        time.sleep(1)
