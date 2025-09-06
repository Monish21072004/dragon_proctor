import pyaudio
import numpy as np
import time
import threading
import wave
import os
from datetime import datetime
import logging
from collections import deque


class VoiceDetector:
    """
    A class to continuously monitor audio input, detect voice/sound based on an energy threshold,
    and save recordings of detected events.
    """

    def __init__(self, callback=None, threshold=0.0002, chunk_size=1024, rate=44100):
        """
        Initializes the VoiceDetector.

        Args:
            callback (function, optional): A function to call when a voice event is detected. Defaults to None.
            threshold (float, optional): The initial energy threshold for voice detection. Defaults to 0.0002.
            chunk_size (int, optional): The number of frames per buffer. Defaults to 1024.
            rate (int, optional): The sample rate. Defaults to 44100.
        """
        self.callback = callback
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.rate = rate
        self.format = pyaudio.paInt16
        self.channels = 1

        self.event_log = []
        self.risk_score = 0
        self.is_running = False
        self.thread = None

        try:
            self.p = pyaudio.PyAudio()
            logging.info("PyAudio initialized successfully for VoiceDetector")
        except Exception as e:
            logging.error(f"Error initializing PyAudio: {str(e)}")
            self.p = None

        self.recordings_dir = os.path.join("static", "recordings")
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)

    def calibrate_threshold(self, seconds=3):
        """
        Calibrates the detection threshold based on ambient noise.

        Args:
            seconds (int, optional): The duration of calibration in seconds. Defaults to 3.
        """
        if self.p is None: return
        logging.info("Calibrating voice threshold...")
        stream = self.p.open(format=self.format, channels=self.channels, rate=self.rate,
                             input=True, frames_per_buffer=self.chunk_size)
        frames = []
        for _ in range(int(self.rate / self.chunk_size * seconds)):
            try:
                frames.append(stream.read(self.chunk_size, exception_on_overflow=False))
            except IOError as ex:
                logging.warning(f"IOError during calibration: {ex}")

        stream.stop_stream()
        stream.close()

        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
        ambient_energy = np.abs(audio_data).mean()
        # FIX: Increased multiplier to 3.5 to make it less sensitive to background noise.
        self.threshold = (ambient_energy / 32767.0) * 3.5
        logging.info(f"Calibration complete. New threshold: {self.threshold:.4f}")

    def _monitor_voice(self):
        """The main monitoring loop that runs in a background thread."""
        if self.p is None: return
        stream = self.p.open(format=self.format, channels=self.channels, rate=self.rate,
                             input=True, frames_per_buffer=self.chunk_size)

        logging.info("Continuous voice monitoring started.")
        frames = []
        is_recording = False
        silence_counter = 0

        # FIX: Add a buffer to capture audio just before the trigger
        # Buffer for about 1 second of audio
        buffer_size = int(self.rate / self.chunk_size * 1)
        audio_buffer = deque(maxlen=buffer_size)

        while self.is_running:
            try:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                audio_buffer.append(data)  # Always keep the buffer full

                audio_chunk = np.frombuffer(data, dtype=np.int16)
                energy = np.abs(audio_chunk).mean() / 32767.0

                if is_recording:
                    frames.append(data)
                    if energy < self.threshold:
                        silence_counter += 1
                        # Stop recording after ~2 seconds of silence
                        if silence_counter > (self.rate / self.chunk_size * 2):
                            self._save_recording(frames)
                            frames = []
                            is_recording = False
                            silence_counter = 0
                    else:
                        silence_counter = 0

                elif energy > self.threshold:
                    logging.info(f"Voice detected! Energy: {energy:.4f} > Threshold: {self.threshold:.4f}")
                    is_recording = True
                    # Start recording with the pre-trigger buffer to capture the whole sound
                    frames.extend(list(audio_buffer))

            except IOError as ex:
                logging.warning(f"IOError during monitoring: {ex}")
                # Reset state on error to avoid corruption
                audio_buffer.clear()
                frames = []
                is_recording = False

        stream.stop_stream()
        stream.close()

    def _save_recording(self, frames):
        """Saves the recorded audio frames to a WAV file and logs the event."""
        # FIX: Prevent saving empty or very short, unplayable files
        if not frames or len(frames) < 10:  # Requires at least a small number of frames
            logging.warning("Attempted to save an empty or too-short recording.")
            return

        duration = len(frames) * self.chunk_size / self.rate
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{timestamp}.wav"
        filepath_web = os.path.join(self.recordings_dir, filename).replace('\\', '/')
        filepath_os = os.path.join(self.recordings_dir, filename)

        risk_increment = 10 + (int(duration) * 5)
        self.risk_score += risk_increment

        event = {
            "timestamp": time.time(),
            "event": "Human Voice Detected",
            "duration": round(duration, 2),
            "risk_score": risk_increment,
            "recording_file": filepath_web
        }
        self.event_log.append(event)
        if self.callback:
            self.callback(event)

        try:
            with wave.open(filepath_os, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.p.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))
            logging.info(f"Saved recording: {filename}, Duration: {duration:.2f}s, Risk: +{risk_increment}")
        except Exception as e:
            logging.error(f"Failed to save WAV file {filename}: {e}")

    def start(self):
        """Starts the voice monitoring thread."""
        if self.p is None:
            logging.error("Cannot start VoiceDetector, PyAudio not available.")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_voice, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the voice monitoring thread."""
        self.is_running = False
        if self.thread:
            self.thread.join()
        if self.p:
            self.p.terminate()
        logging.info("VoiceDetector stopped.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(asctime)s - %(name)s: %(message)s')


    def test_callback(event):
        print(f"EVENT DETECTED: {event}")


    detector = VoiceDetector(callback=test_callback)
    detector.calibrate_threshold()
    detector.start()

    print("Voice detector is running. Speak to trigger a recording. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        detector.stop()
        print("\nVoice detector stopped.")
