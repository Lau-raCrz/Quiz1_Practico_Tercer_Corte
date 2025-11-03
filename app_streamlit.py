import streamlit as st
import cv2
import mediapipe as mp

st.set_page_config(page_title="Detección de Postura", layout="centered")

# === Configuración de MediaPipe ===
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# === Función para clasificar la postura ===
def clasificar_postura(landmarks):
    left_hip = landmarks[23]
    right_hip = landmarks[24]
    left_knee = landmarks[25]
    right_knee = landmarks[26]
    hip_y = (left_hip.y + right_hip.y) / 2
    knee_y = (left_knee.y + right_knee.y) / 2
    diff = knee_y - hip_y
    return "🧍 De pie" if diff >= 0.15 else "🪑 Sentado"

# === Interfaz Streamlit ===
st.title("🧠 Detección de Postura en Tiempo Real")
st.write("Este sistema usa **MediaPipe** para detectar si estás de pie o sentado.")

start = st.button("Iniciar detección")

frame_placeholder = st.empty()
status_placeholder = st.empty()

if start:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        st.error("❌ No se pudo acceder a la cámara. Verifica permisos o dispositivos ocupados.")
    else:
        stop_button = st.button("Detener", key="stop_button")
        while True:
            ret, frame = cap.read()
            if not ret:
                st.warning("No se pudo leer la cámara.")
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(frame_rgb)

            posture = "No detectada"
            if results.pose_landmarks:
                posture = clasificar_postura(results.pose_landmarks.landmark)
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            frame_placeholder.image(frame, channels="BGR")
            status_placeholder.markdown(f"### Postura actual: **{posture}**")

            # Si el botón de detener fue presionado, rompemos el bucle
            if stop_button:
                break

        cap.release()
        st.success("✅ Detección detenida correctamente.")
