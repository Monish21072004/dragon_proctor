import pyaudio
import numpy as np
import time
import threading
import wave
import os
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(filename='voice_detector.log', level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class VoiceDetector:
    def __init__(self, callback=None, threshold=0.0002, record_seconds=10):
        self.callback = callback
        self.threshold = threshold
        self.record_seconds = record_seconds
        self.event_log = []
        self.is_running = False
        
        try:
            self.p = pyaudio.PyAudio()
            logging.info("PyAudio initialized successfully")
        except Exception as e:
            logging.error(f"Error initializing PyAudio: {str(e)}")
            self.p = None
            
        self.recordings_dir = os.path.join("static", "recordings")
        
        try:
            if not os.path.exists(self.recordings_dir):
                os.makedirs(self.recordings_dir)
                logging.info(f"Created recordings directory: {self.recordings_dir}")
        except Exception as e:
            logging.error(f"Error creating recordings directory: {str(e)}")

    def calibrate_threshold(self, calibration_seconds=3):
        """Calibrate the threshold based on ambient noise"""
        if self.p is None:
            return
            
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        
        try:
            stream = self.p.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)
            frames = []
            
            for _ in range(0, int(RATE / CHUNK * calibration_seconds)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
            energy = np.abs(audio_data).mean()
            self.threshold = (energy / 32767) * 1.5  # 1.5x ambient noise
            logging.info(f"Calibrated threshold to {self.threshold}")
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logging.error(f"Calibration failed: {str(e)}")

    def detect_voice(self):
        """Record audio and detect voice with dynamic silence detection"""
        if self.p is None:
            return False, None
            
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        frames = []
        silent_frames = 0
        max_silent_frames = int(RATE / CHUNK * 2)  # 2 seconds of allowed silence
        
        try:
            stream = self.p.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)
            
            logging.info("Recording started with dynamic silence detection")
            print("Recording... Speak now")
            
            for _ in range(0, int(RATE / CHUNK * self.record_seconds)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                # Real-time energy analysis
                audio_chunk = np.frombuffer(data, dtype=np.int16)
                chunk_energy = np.abs(audio_chunk).mean()
                
                if chunk_energy < self.threshold * 32767:
                    silent_frames += 1
                    if silent_frames > max_silent_frames:
                        logging.info("Too much silence, stopping early")
                        break
                else:
                    silent_frames = 0
                    
            stream.stop_stream()
            stream.close()

        except Exception as e:
            logging.error(f"Recording error: {str(e)}")
            return False, None

        # Save recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{timestamp}.wav"
        filepath = os.path.join(self.recordings_dir, filename)
        
        try:
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.p.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))
                
            audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
            energy = np.abs(audio_data).mean()
            has_voice = energy > self.threshold * 32767
            
            if has_voice:
                event = {
                    "timestamp": time.time(),
                    "event": "Human Voice Detected",
                    "energy_level": float(energy),
                    "recording_file": filename
                }
                self.event_log.append(event)
                if self.callback:
                    self.callback(event)
            
            return has_voice, filename if has_voice else None
            
        except Exception as e:
            logging.error(f"Saving/Analysis error: {str(e)}")
            return False, None
