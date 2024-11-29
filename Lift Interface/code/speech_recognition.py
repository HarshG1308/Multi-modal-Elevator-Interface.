import threading
import pyaudio
import json
from vosk import Model, KaldiRecognizer

class SpeechRecognition:
    def __init__(self, app):
        self.app = app
        self.stop_processing = False
        self.thread = None
        self.setup()

    def setup(self):
        model_path = r"Lift Interface\code\vosk-model-en-in-0.5"
        self.grammar = {
            "type": "list",
            "items": [
                "one", "two", "three", "four", "five",
                "six", "seven", "eight", "nine", "ten",
                "open", "close", "emergency",
                "first", "second", "third", "fourth", "fifth",
                "sixth", "seventh", "eighth", "ninth", "tenth"
            ]
        }

        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000, json.dumps(self.grammar))

        self.number_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
            "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
        }

    def start(self):
        self.stop_processing = False
        self.thread = threading.Thread(target=self._recognition_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_processing = True
        if self.thread:
            self.thread.join(timeout=1)

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()
    
    def update_status(self, status):
        self.app.root.after(0, self.app.update_status, status)

    def _recognition_loop(self):
        p = pyaudio.PyAudio()
        print("Listening...")
        self.update_status("Listening...")
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        stream.start_stream()

        while not self.stop_processing:
            data = stream.read(4000, exception_on_overflow=False)
            if self.recognizer.AcceptWaveform(data):
                result = self.recognizer.Result()
                text = json.loads(result).get("text", "")
                if text:
                    self.app.root.after(0, self.handle_command, text)

        stream.stop_stream()
        stream.close()
        p.terminate()

    def handle_command(self, command):
        print(f"Recognized: {command}")
        target_floor = 0
        for word, number in self.number_map.items():
            if word in command:
                target_floor = number
                break
        if "open" in command:
            self.app.open_door()
        elif "close" in command:
            self.app.close_door()
        elif "emergency" in command:
            self.app.simulate_emergency()
        elif target_floor > 0:
            if target_floor > self.app.max_floors or target_floor < 1:
                self.app.speak("Invalid floor number")
            else:
                self.app.handle_floor_button(target_floor)