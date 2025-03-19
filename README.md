# Dragon Eye Examiner Proctoring System

## Introduction
Dragon Eye Examiner is a cutting-edge online exam proctoring system designed to maintain academic integrity in remote testing environments. With the rise of online education and remote examinations, ensuring that candidates adhere to exam protocols has become a significant challenge. Our solution leverages real-time computer vision, deep learning-based emotion recognition, voice detection, and behavioral tracking to monitor exam takers continuously. By combining multiple monitoring modalities into a single risk scoring framework, Dragon Eye Examiner detects suspicious behavior and triggers alerts, helping institutions maintain a fair and secure testing environment.

## Key Features

- **Real-Time Face & Eye Detection**  
  - **Presence Monitoring:** Continuously checks that a candidate is present in front of the webcam.  
  - **Eye Alignment:** Detects abnormal eye alignment to infer if a candidate is frequently looking away, potentially indicating cheating or distraction.  
  - **Multiple Face Detection:** Identifies the presence of additional faces in the frame.

- **Emotion Recognition**  
  - **Deep Learning Analysis:** Utilizes pre-trained deep neural networks to analyze facial expressions in real time.  
  - **Emotion Alerts:** Detects critical emotions (such as fear, anxiety, or stress) that may indicate exam-related distress or potential misconduct.

- **Voice Detection**  
  - **Audio Monitoring:** Captures ambient audio using the system’s microphone to detect unauthorized communication.  
  - **Voice Activity Detection:** Uses voice activity detection algorithms to trigger alerts if extraneous voices are present.

- **Behavioral Tracking**  
  - **Mouse & Window Tracking:** Monitors mouse movements, window switching, and copy events to flag unusual activity.  
  - **Risk Aggregation:** Aggregates behavioral data into a unified risk score to trigger alerts if suspicious behavior persists.

- **Network Lockdown**  
  - **Access Control:** Restricts access to unauthorized resources during the exam, minimizing the chance of online cheating.

- **Data Logging & Reporting**  
  - **Event Logging:** Maintains detailed logs of all proctoring activities, including timestamps and risk contributions.  
  - **CSV Export:** Provides options to export event logs for audit trails and further analysis.

## Technologies and Tools

- **Programming Languages & Frameworks:**  
  - Python (with Flask for the web dashboard and OpenCV for image processing)
  - TensorFlow & Keras for deep learning-based emotion recognition

- **Computer Vision & Audio Analysis:**  
  - OpenCV, MTCNN for face and eye detection
  - MediaRecorder API & webrtcvad for voice detection

- **DevOps & CI/CD:**  
  - Docker for containerization
  - GitHub Actions for continuous integration and deployment
  - Terraform/Ansible for Infrastructure as Code (IaC)

- **Monitoring & Logging:**  
  - Prometheus and Grafana for real-time monitoring
  - ELK stack or Fluentd for centralized logging

## Project Structure

```plaintext
dragon-eye-examiner/
├── app.py                     # Main Flask application
├── face_detector.py           # Module for face, eye, and emotion detection
├── voice_detector.py          # Module for voice detection
├── mouse_tracker.py           # Module for mouse tracking
├── window_tracker.py          # Module for window activity tracking
├── copy_tracker.py            # Module for copy event tracking
├── peripheral_detector.py     # Module for peripheral detection
├── requirements.txt           # Python package dependencies
├── Dockerfile                 # Docker configuration for containerization
├── .github/workflows/ci-cd.yml  # CI/CD pipeline configuration (GitHub Actions)
├── CONTRIBUTING.md            # Contribution guidelines and branching strategy
└── README.md                  # Project documentation (this file)

