from flask import Flask, render_template, jsonify, Response, request
import threading
from io import StringIO, BytesIO
import csv
import time
import logging
import os
from pynput import keyboard
import matplotlib.pyplot as plt

# Import trackers and detectors.
from mouse_tracker import MouseBehaviorTracker
from window_tracker import WindowTracker
from copy_tracker import CopyTracker
from network_lockdown import NetworkLockdown
from peripheral_detector import PeripheralDetector

# Import the updated face_detector module.
import face_detector

# Import the voice_detector module.
from voice_detector import VoiceDetector

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

def mouse_event_callback(event):
    logging.info("Mouse Event: " + str(event))

def window_event_callback(event):
    logging.info("Window Event: " + str(event))

def copy_event_callback(event):
    logging.info("Copy Event: " + str(event))

def peripheral_event_callback(event):
    logging.info("Peripheral Event: " + str(event))

def voice_event_callback(event):
    logging.info("Voice Event: " + str(event))

# Initialize trackers.
mouse_tracker = MouseBehaviorTracker(speed_threshold=1500, angle_threshold=90, callback=mouse_event_callback)
window_tracker = WindowTracker(poll_interval=0.5, callback=window_event_callback)
copy_tracker = CopyTracker(poll_interval=1.0, callback=copy_event_callback)
network_lockdown = NetworkLockdown(allowed_exe="C:\\Path\\to\\exam_browser.exe")
peripheral_detector = PeripheralDetector(callback=peripheral_event_callback)

# Initialize and calibrate VoiceDetector.
voice_detector = VoiceDetector(callback=voice_event_callback, threshold=0.0002)
voice_detector.calibrate_threshold()

def get_status(score):
    # You may adjust these thresholds as needed.
    if score >= 100:
        return "Direct kick out"
    elif score >= 80:
        return "Warning-2"
    elif score >= 70:
        return "Warning-1"
    else:
        return "Safe"

# Routes for pages.
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/risk')
def risk_page():
    return render_template('risk.html')

@app.route('/copy_test')
def copy_test():
    return render_template('copy_test.html')

@app.route('/face_detection')
def face_detection():
    return render_template('face_detection.html')

@app.route('/video_feed')
def video_feed():
    # Uses the updated face_detector.gen_frames() which now supports frame sampling.
    return Response(face_detector.gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# API endpoints for events.
@app.route('/api/mouse_events')
def api_mouse_events():
    return jsonify(mouse_tracker.event_log)

@app.route('/api/window_events')
def api_window_events():
    return jsonify(window_tracker.event_log)

@app.route('/api/copy_events')
def api_copy_events():
    return jsonify(copy_tracker.event_log)

@app.route('/api/peripheral_events')
def api_peripheral_events():
    return jsonify(peripheral_detector.event_log)

@app.route('/api/face_risk')
def api_face_risk():
    # Accesses updated globals from face_detector.
    return jsonify({
        "face_risk": face_detector.eye_risk_score,
        "face_events": face_detector.eye_risk_events,
        "scoring_started": face_detector.scoring_started
    })

@app.route('/api/risk')
def api_risk():
    mouse_risk = 0
    window_risk = window_tracker.risk_score if hasattr(window_tracker, 'risk_score') else 0
    copy_risk = copy_tracker.risk_score if hasattr(copy_tracker, 'risk_score') else 0
    peripheral_risk = peripheral_detector.risk_score if hasattr(peripheral_detector, 'risk_score') else 0
    face_risk = face_detector.eye_risk_score
    voice_risk = voice_detector.risk_score if hasattr(voice_detector, 'risk_score') else 0

    aggregate = mouse_risk + window_risk + copy_risk + peripheral_risk + face_risk + voice_risk

    # Set kickout flag if aggregate risk is 1000 or higher.
    kickout_flag = True if aggregate >= 1000 else False

    return jsonify({
        "mouse_risk": mouse_risk,
        "mouse_status": get_status(mouse_risk),
        "window_risk": window_risk,
        "window_status": get_status(window_risk),
        "copy_risk": copy_risk,
        "copy_status": get_status(copy_risk),
        "peripheral_risk": peripheral_risk,
        "peripheral_status": get_status(peripheral_risk),
        "face_risk": face_risk,
        "face_status": get_status(face_risk),
        "voice_risk": voice_risk,
        "voice_status": get_status(voice_risk),
        "aggregate": aggregate,
        "aggregate_status": get_status(aggregate),
        "kickout": kickout_flag
    })

@app.route('/api/register_copy', methods=['POST'])
def register_copy():
    data = request.json
    if data and 'content' in data:
        content = data['content']
        word_count = len(content.split())
        event = {
            "timestamp": time.time(),
            "event": "Copy-Paste (Client)",
            "content_preview": content[:50],
            "word_count": word_count,
            "full_content": content
        }
        copy_tracker.event_log.append(event)
        logging.info("Registered copy event: " + str(event))
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/network_lockdown', methods=['GET'])
def api_network_lockdown():
    state = request.args.get("state", "").lower()
    if state == "on":
        network_lockdown.activate()
        return jsonify({"status": "lockdown activated"}), 200
    elif state == "off":
        network_lockdown.deactivate()
        return jsonify({"status": "lockdown deactivated"}), 200
    else:
        return jsonify({"status": "invalid state"}), 400

@app.route('/api/shortcuts', methods=['GET'])
def api_shortcuts():
    state = request.args.get("state", "").lower()
    if state == "disable":
        result = copy_tracker.disable_shortcuts()
        if result:
            return jsonify({"status": "shortcuts disabled"}), 200
        else:
            return jsonify({"status": "shortcuts already disabled"}), 200
    elif state == "enable":
        result = copy_tracker.enable_shortcuts()
        if result:
            return jsonify({"status": "shortcuts enabled"}), 200
        else:
            return jsonify({"status": "shortcuts already enabled"}), 200
    else:
        return jsonify({"status": "invalid state, use 'disable' or 'enable'"}), 400

@app.route('/api/stop_video', methods=['GET'])
def stop_video_endpoint():
    face_detector.stop_video()
    return jsonify({"status": "video stream stopped"}), 200

@app.route('/api/test_voice_detection', methods=['POST'])
def test_voice_detection():
    try:
        has_voice, recording_file = voice_detector.detect_voice()
        return jsonify({
            "voice_detected": has_voice,
            "recording_path": recording_file if has_voice else None
        })
    except Exception as e:
        logging.error(f"Error in voice detection API: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/voice_events')
def voice_events():
    logging.info("Voice event log: " + str(voice_detector.event_log))
    return jsonify(voice_detector.event_log)

# CSV Export Endpoints.
@app.route('/download/mouse_csv')
def download_mouse_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'event', 'speed', 'angle_diff', 'position'])
    for event in mouse_tracker.event_log:
        cw.writerow([
            event.get('timestamp', ''),
            event.get('event', ''),
            event.get('speed', ''),
            event.get('angle_diff', ''),
            event.get('position', '')
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=mouse_events.csv"})

@app.route('/download/window_csv')
def download_window_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'window', 'duration'])
    for event in window_tracker.event_log:
        cw.writerow([
            event.get('timestamp', ''),
            event.get('window', ''),
            event.get('duration', '')
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=window_events.csv"})

@app.route('/download/copy_csv')
def download_copy_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'event', 'content_preview', 'word_count', 'full_content'])
    for event in copy_tracker.event_log:
        cw.writerow([
            event.get('timestamp', ''),
            event.get('event', ''),
            event.get('content_preview', ''),
            event.get('word_count', ''),
            event.get('full_content', '')
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=copy_events.csv"})

@app.route('/download/peripheral_csv')
def download_peripheral_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'device'])
    for event in peripheral_detector.event_log:
        cw.writerow([
            event.get('timestamp', ''),
            event.get('device', event.get('Caption', 'Unknown'))
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=peripheral_events.csv"})

@app.route('/download/face_csv')
def download_face_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'event', 'risk', 'details'])
    for event in face_detector.eye_risk_events:
        details = ""
        if "faces_detected" in event:
            details = f"Faces: {event['faces_detected']}"
        elif "duration" in event:
            details = f"Duration: {event['duration']:.2f} s, intervals: {event.get('intervals', '')}"
        elif "vertical_diff" in event:
            details = f"Vertical diff: {event['vertical_diff']:.2f}"
        elif "left_eye_x" in event and "right_eye_x" in event:
            details = f"Horizontal alignment: left_eye_x={event['left_eye_x']}, right_eye_x={event['right_eye_x']}"
        cw.writerow([event.get('timestamp', ''), event.get('event', ''), event.get('risk', ''), details])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=face_events.csv"})

@app.route('/download/voice_csv')
def download_voice_csv():
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['timestamp', 'event', 'duration', 'risk_score', 'recording_file'])
    for event in voice_detector.event_log:
        cw.writerow([
            event.get('timestamp', ''),
            event.get('event', ''),
            event.get('duration', ''),
            event.get('risk_score', ''),
            event.get('recording_file', '')
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=voice_events.csv"})

@app.route('/download/graph_csv')
def download_graph_csv():
    data = []
    for event in face_detector.eye_risk_events:
        data.append({
            "timestamp": event.get("timestamp", ""),
            "risk": event.get("risk", ""),
            "source": "face"
        })
    for event in voice_detector.event_log:
        data.append({
            "timestamp": event.get("timestamp", ""),
            "risk": event.get("risk_score", ""),
            "source": "voice"
        })
    data.sort(key=lambda x: x["timestamp"])
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["timestamp", "risk", "source"])
    for item in data:
        cw.writerow([item["timestamp"], item["risk"], item["source"]])
    output = si.getvalue()
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=graph_data.csv"})

# Graph endpoints using Matplotlib.
@app.route('/graph/<event_type>')
def graph_event(event_type):
    if event_type == 'mouse':
        events = mouse_tracker.event_log
    elif event_type == 'window':
        events = window_tracker.event_log
    elif event_type == 'copy':
        events = copy_tracker.event_log
    elif event_type == 'peripheral':
        events = peripheral_detector.event_log
    elif event_type == 'face':
        events = face_detector.eye_risk_events
    elif event_type == 'voice':
        events = voice_detector.event_log
    else:
        return "Invalid event type", 400

    times = []
    values = []
    for event in events:
        t = event.get('timestamp')
        if t is not None:
            times.append(t)
            # For face events, use 'risk'; otherwise, default to 1.
            val = event.get('risk', 1)
            values.append(val)
    if not times:
        return "No data available", 404

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(times, values, marker='o', linestyle='-', color='cyan')
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Risk Value' if any('risk' in e for e in events) else 'Event Count')
    ax.set_title(f'{event_type.capitalize()} Events Graph')
    ax.grid(True)
    fig.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return Response(buf.getvalue(), mimetype='image/png')

# Kickout route.
@app.route('/kickout')
def kickout():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Kicked Out</title>
      <style>
        body { background-color: #1a1a1a; color: #fff; text-align: center; padding-top: 50px; }
        h1 { font-size: 3em; }
      </style>
    </head>
    <body>
      <h1>You have been kicked out.</h1>
      <p>Your overall risk score exceeded the allowed threshold.</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    import webbrowser
    url = "http://127.0.0.1:5000/"
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()

    # Start the trackers in separate threads.
    threading.Thread(target=mouse_tracker.start, daemon=True).start()
    threading.Thread(target=window_tracker.start, daemon=True).start()
    threading.Thread(target=copy_tracker.start, daemon=True).start()
    threading.Thread(target=peripheral_detector.start, daemon=True).start()

    app.run(debug=True)
