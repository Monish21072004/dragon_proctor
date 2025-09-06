import cv2
import torch
from facenet_pytorch import MTCNN
import time
import logging
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.utils import img_to_array

# Setup logging.
logger = logging.getLogger("FaceDetector")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Use GPU if available.
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
mtcnn = MTCNN(keep_all=True, device=device)

# Global risk score and event log.
eye_risk_score = 0
eye_risk_events = []

# Load the emotion detection model (trained on the FER dataset).
emotion_model = load_model("emotion-detect.keras")
emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Tracking variables.
prev_extra_faces = 0
extra_face_start_time = None
extra_face_stable_count = 0  # Count consecutive frames with extra faces.
no_face_start_time = None

# Flag to start scoring only after a person is detected and a wait period passes.
scoring_started = False
detection_start_time = None
WAIT_TIME = 5  # seconds

# Risk parameters.
EXTRA_FACE_IMMEDIATE_RISK = 25
EXTRA_FACE_TIME_RISK_PER_10SEC = 10
LOOKING_AWAY_TIME_RISK_PER_10SEC = 10
EYE_ALIGNMENT_THRESHOLD = 10
EYE_ALIGNMENT_RISK = 5
EMOTION_RISK = 1  # Additional risk if emotion is Fear, Sad, or Angry
FRAME_PROCESS_RATE = 5  # Process every 5th frame for risk scoring

cap = None  # Global variable for video capture.

def process_frame(frame):
    global eye_risk_score, eye_risk_events, prev_extra_faces, extra_face_start_time, extra_face_stable_count
    global no_face_start_time, scoring_started, detection_start_time

    current_time = time.time()
    # Convert frame from BGR to RGB.
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes, probs, landmarks = mtcnn.detect(img_rgb, landmarks=True)

    # CASE 1: No face detected.
    if boxes is None or len(boxes) == 0:
        if not scoring_started:
            return frame
        if no_face_start_time is None:
            no_face_start_time = current_time
        else:
            duration = current_time - no_face_start_time
            if duration >= 10:
                intervals = int(duration // 10)
                looking_away_risk = intervals * LOOKING_AWAY_TIME_RISK_PER_10SEC
                eye_risk_score += looking_away_risk
                eye_risk_events.append({
                    "timestamp": current_time,
                    "event": "Looking Away",
                    "risk": looking_away_risk,
                    "duration": duration,
                    "intervals": intervals
                })
                logger.info("No face detected for %.2f sec (%d intervals); looking away risk +%d",
                            duration, intervals, looking_away_risk)
                no_face_start_time += 10 * intervals
        # Reset extra face tracking.
        prev_extra_faces = 0
        extra_face_start_time = None
        extra_face_stable_count = 0
        return frame

    # CASE 2: Face detected.
    if not scoring_started:
        scoring_started = True
        detection_start_time = current_time
        logger.info("Face detected. Waiting %d seconds to start risk scoring.", WAIT_TIME)
        return frame
    if current_time - detection_start_time < WAIT_TIME:
        return frame

    # Reset no-face timer.
    no_face_start_time = None
    current_delta = 0

    # Calculate extra face count (if more than one face is detected).
    current_extra_faces = max(len(boxes) - 1, 0)
    if current_extra_faces > 0:
        if current_extra_faces == prev_extra_faces:
            extra_face_stable_count += 1
        else:
            extra_face_stable_count = 1
            extra_face_start_time = current_time
            immediate_risk = current_extra_faces * EXTRA_FACE_IMMEDIATE_RISK
            current_delta += immediate_risk
            eye_risk_events.append({
                "timestamp": current_time,
                "event": "Multiple Faces Detected",
                "risk": immediate_risk,
                "faces_detected": len(boxes)
            })
            logger.info("Detected %d faces (%d extra); immediate risk +%d",
                        len(boxes), current_extra_faces, immediate_risk)
        if extra_face_stable_count >= 2 and extra_face_start_time is not None:
            duration = current_time - extra_face_start_time
            if duration >= 10:
                intervals = int(duration // 10)
                extra_time_risk = current_extra_faces * EXTRA_FACE_TIME_RISK_PER_10SEC * intervals
                current_delta += extra_time_risk
                eye_risk_events.append({
                    "timestamp": current_time,
                    "event": "Extra Face Duration",
                    "risk": extra_time_risk,
                    "duration": duration,
                    "intervals": intervals
                })
                logger.info("Extra faces stable for %.2f sec (%d intervals); additional risk +%d",
                            duration, intervals, extra_time_risk)
                extra_face_start_time += 10 * intervals
        prev_extra_faces = current_extra_faces
    else:
        prev_extra_faces = 0
        extra_face_start_time = None
        extra_face_stable_count = 0

    # Process each detected face.
    if boxes is not None:
        for box in boxes:
            box = [int(b) for b in box]
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
            # Crop face ROI.
            face_roi = frame[box[1]:box[3], box[0]:box[2]]
            try:
                face_gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
                face_resized = cv2.resize(face_gray, (48, 48))
            except Exception as e:
                logger.error("Error processing face ROI: %s", str(e))
                continue
            face_resized = face_resized.astype("float") / 255.0
            face_resized = img_to_array(face_resized)  # Shape: (48, 48, 1)
            # Adjust for models expecting 3 channels.
            if emotion_model.input_shape[-1] == 3:
                face_resized = np.repeat(face_resized, 3, axis=-1)
            face_resized = np.expand_dims(face_resized, axis=0)
            preds = emotion_model.predict(face_resized)[0]
            emotion_label = emotion_labels[preds.argmax()]
            cv2.putText(frame, emotion_label, (box[0], box[1]-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
            # Increase risk for critical emotions, otherwise log with 0 risk.
            if emotion_label in ["Fear", "Sad", "Angry"]:
                current_delta += EMOTION_RISK
                eye_risk_events.append({
                    "timestamp": current_time,
                    "event": f"Emotion Detected: {emotion_label}",
                    "risk": EMOTION_RISK
                })
                logger.info("Emotion %s detected; risk +%d", emotion_label, EMOTION_RISK)
            else:
                eye_risk_events.append({
                    "timestamp": current_time,
                    "event": f"Emotion Detected: {emotion_label}",
                    "risk": 0
                })
                logger.info("Emotion %s detected; no additional risk", emotion_label)

    # Enhanced eye alignment check using landmarks.
    if landmarks is not None:
        for face_landmarks in landmarks:
            if face_landmarks is not None and len(face_landmarks) >= 2:
                left_eye, right_eye = face_landmarks[0], face_landmarks[1]
                cv2.circle(frame, (int(left_eye[0]), int(left_eye[1])), 3, (255, 0, 0), -1)
                cv2.circle(frame, (int(right_eye[0]), int(right_eye[1])), 3, (255, 0, 0), -1)
                # Vertical alignment check.
                vertical_diff = abs(left_eye[1] - right_eye[1])
                if vertical_diff > EYE_ALIGNMENT_THRESHOLD:
                    current_delta += EYE_ALIGNMENT_RISK
                    eye_risk_events.append({
                        "timestamp": current_time,
                        "event": "Abnormal Eye Vertical Alignment",
                        "risk": EYE_ALIGNMENT_RISK,
                        "vertical_diff": vertical_diff
                    })
                    logger.info("Abnormal vertical eye alignment (diff=%.2f px); risk +%d",
                                vertical_diff, EYE_ALIGNMENT_RISK)
                # Horizontal alignment: ensure left eye is to the left of right eye.
                if left_eye[0] >= right_eye[0]:
                    current_delta += EYE_ALIGNMENT_RISK
                    eye_risk_events.append({
                        "timestamp": current_time,
                        "event": "Abnormal Eye Horizontal Alignment",
                        "risk": EYE_ALIGNMENT_RISK,
                        "left_eye_x": left_eye[0],
                        "right_eye_x": right_eye[0]
                    })
                    logger.info("Abnormal horizontal eye alignment (left_eye_x=%d, right_eye_x=%d); risk +%d",
                                int(left_eye[0]), int(right_eye[0]), EYE_ALIGNEMENT_RISK)

    eye_risk_score += current_delta
    logger.debug("Frame processed: risk increment = %d, total risk = %d", current_delta, eye_risk_score)
    return frame

def gen_frames():
    global cap
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Cannot open webcam.")
        return
    frame_counter = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to capture frame.")
            break
        frame_counter += 1
        # Process every FRAME_PROCESS_RATE-th frame.
        if frame_counter % FRAME_PROCESS_RATE == 0:
            frame = process_frame(frame)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def stop_video():
    global cap
    if cap is not None:
        cap.release()
        cap = None
        logger.info("Camera has been released.")
