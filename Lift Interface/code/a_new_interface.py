import csv
import json
import math
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import queue
import pyaudio
import pyttsx3
import tobii_research as tr
from vosk import KaldiRecognizer, Model

class MovingAverageFilter:
    def __init__(self, window_size=5):
        self.window_size = window_size
        self.data_x = []
        self.data_y = []

    def update(self, x, y):
        self.data_x.append(x)
        self.data_y.append(y)
        if len(self.data_x) > self.window_size:
            self.data_x.pop(0)
            self.data_y.pop(0)

    def get_average(self):
        if not self.data_x or not self.data_y:
            return None, None
        return sum(self.data_x) / len(self.data_x), sum(self.data_y) / len(self.data_y)

class EyeGazePointer(tk.Toplevel):
    def __init__(self, master, eyetracker):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.7)
        
        self.canvas = tk.Canvas(self, bg='white', width=20, height=20, highlightthickness=0)
        self.canvas.pack()
        
        self.pointer = self.canvas.create_oval(0, 0, 20, 20, fill='red')
        
        self.prev_screen_x = None
        self.prev_screen_y = None
        self.smoothing_factor = 0.3

        self.eyetracker = eyetracker
        self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback, as_dictionary=True)

    def gaze_data_callback(self, gaze_data):
        left_gaze_point = gaze_data['left_gaze_point_on_display_area']
        right_gaze_point = gaze_data['right_gaze_point_on_display_area']

        if left_gaze_point and right_gaze_point:
            gaze_x = (left_gaze_point[0] + right_gaze_point[0]) / 2
            gaze_y = (left_gaze_point[1] + right_gaze_point[1]) / 2
        elif left_gaze_point:
            gaze_x, gaze_y = left_gaze_point
        elif right_gaze_point:
            gaze_x, gaze_y = right_gaze_point
        else:
            return

        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        screen_x = int(gaze_x * screen_width)
        screen_y = int(gaze_y * screen_height)

        if self.prev_screen_x is not None and self.prev_screen_y is not None:
            screen_x = int(self.smoothing_factor * screen_x + (1 - self.smoothing_factor) * self.prev_screen_x)
            screen_y = int(self.smoothing_factor * screen_y + (1 - self.smoothing_factor) * self.prev_screen_y)

        self.prev_screen_x, self.prev_screen_y = screen_x, screen_y

        self.geometry(f"20x20+{screen_x-10}+{screen_y-10}")

    def close(self):
        self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)
        self.destroy()

class ElevatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Elevator Interface")
        self.root.geometry("800x600")
        self.root.configure(bg="white")

        self.max_floors = 9
        self.coordinates = []
        self.current_floor = 1
        self.door_status = "Closed"
        self.stop_processing = False
        self.slider = None
        self.selected_floor = None
        self.elevator_moving = False
        self.emergency_triggered = False
        self.eye_tracking_queue = queue.Queue()
        self.root.after(100, self.process_eye_tracking_queue)
        
        self.open_button_frame = None
        self.close_button_frame = None
        self.emergency_button_frame = None
        self.open_button = None
        self.close_button = None
        self.emergency_button = None
        self.eye_gaze_pointer = None
        
        self.active_modality = None
        self.update_ui()

        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)

        self.current_modality = tk.StringVar()
        self.current_modality.set("Mouse Control")

        self.eye_tracker = None
        self.eye_tracking_available = False
        self.gaze_filter = MovingAverageFilter(window_size=5)
        self.track_box = None

        self.voice_thread = None
        self.eye_tracker_thread = None
        
        self.start_time = time.time()
        self.command_count = 0
        self.all_data = {
            "Command": [], "Timestamp": [], "Frames": [], "TER": [], "ITRbuttons": [],
            "meanx": [], "meany": [], "stdx": [], "stdy": [],
            "meanlp": [], "meanrp": [], "stdlp": [], "stdrp": [], "floor": []
        }
        self.last_command_time = time.time()

        self.setup_gui()

    def setup_gui(self):
        heading_label = tk.Label(self.root, text="Elevator Interface", font=("Arial", 24, "bold"), bg="white", fg="black")
        heading_label.pack(pady=5)

        self.setup_modality_dropdown()

        panel_frame = tk.Frame(self.root, bg="white")
        panel_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)   

        self.floor_panel = tk.Frame(panel_frame, bg="white", padx=20, pady=20, bd=5, relief=tk.SUNKEN)
        self.floor_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        floor_panel_label = tk.Label(self.floor_panel, text="Floor Panel", font=("Arial", 16, "bold"), bg="white", fg="black")
        floor_panel_label.pack(pady=10)

        floor_button_frame = tk.Frame(self.floor_panel, bg="white")
        floor_button_frame.pack(pady=10, expand=True)

        self.floor_buttons = []
        for floor in range(1, self.max_floors + 1):
            button_frame = tk.Frame(floor_button_frame, bg="white", bd=3, relief=tk.RAISED)
            button_frame.grid(row=(floor - 1) // 3, column=(floor - 1) % 3, padx=75, pady=8)
            
            button = tk.Button(button_frame, text=f"Floor {floor}", command=lambda f=floor: self.handle_floor_button(f),
                               font=("Arial", 12), bg="black", fg="white", width=10, height=4,
                               activebackground="#333333", activeforeground="white", bd=0)
            button.pack(padx=13, pady=13)
            self.floor_buttons.append((button_frame, button))

        self.open_button_frame = tk.Frame(floor_button_frame, bg="white", bd=3, relief=tk.RAISED)
        self.open_button_frame.grid(row=3, column=0, padx=20, pady=20)
        self.open_button = tk.Button(self.open_button_frame, text="Open\nDoor", command=self.open_door, 
                                font=("Arial", 12), bg="black", fg="white", width=10, height=4,
                                activebackground="#333333", activeforeground="white", bd=0)
        self.open_button.pack(padx=13, pady=13)

        self.close_button_frame = tk.Frame(floor_button_frame, bg="white", bd=3, relief=tk.RAISED)
        self.close_button_frame.grid(row=3, column=1, padx=20, pady=20)
        self.close_button = tk.Button(self.close_button_frame, text="Close\nDoor", command=self.close_door, 
                                 font=("Arial", 12), bg="black", fg="white", width=10, height=4,
                                 activebackground="#333333", activeforeground="white", bd=0)
        self.close_button.pack(padx=13, pady=13)

        self.emergency_button_frame = tk.Frame(floor_button_frame, bg="white", bd=3, relief=tk.RAISED)
        self.emergency_button_frame.grid(row=3, column=2, padx=20, pady=20)
        self.emergency_button = tk.Button(self.emergency_button_frame, text="Emergency", command=self.simulate_emergency, 
                                     font=("Arial", 12), bg="black", fg="white", width=10, height=4,
                                     activebackground="#333333", activeforeground="white", bd=0)
        self.emergency_button.pack(padx=13, pady=13)

        elevator_panel = tk.Frame(panel_frame, bg="white", padx=20, pady=20, bd=2, relief=tk.SUNKEN)
        elevator_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        current_floor_label = tk.Label(elevator_panel, text="Current Floor: ", font=("Arial", 16), bg="white", fg="black")
        current_floor_label.pack(pady=10, side=tk.LEFT, padx=20)

        self.floor_label = tk.Label(elevator_panel, text=str(self.current_floor), font=("Arial", 24), bg="white")
        self.floor_label.pack(pady=10, side=tk.LEFT, padx=20)

        self.arrow_label = tk.Label(elevator_panel, text=" ", font=("Arial", 24), bg="white")
        self.arrow_label.pack(pady=10, side=tk.LEFT, padx=20)

        self.slider = tk.Scale(elevator_panel, from_=self.max_floors, to=1, orient=tk.VERTICAL, length=450, width=60, tickinterval=1, font=("Arial", 12), bg="white", fg="black", highlightthickness=0)
        self.slider.set(self.current_floor)
        self.slider.pack(pady=20)

        door_label = tk.Label(elevator_panel, text="Door: ", font=("Arial", 16), bg="white", fg="black")
        door_label.pack(pady=10, side=tk.LEFT, padx=10)

        self.door_status_label = tk.Label(elevator_panel, text=self.door_status, font=("Arial", 16), bg="white")
        self.door_status_label.pack(pady=10, side=tk.LEFT, padx=10)
        
        self.listening_label = tk.Label(self.root, text="Listening...", font=("Arial", 16), bg="white", fg="black")
        self.listening_label.pack(side=tk.BOTTOM, pady=10)
        self.listening_label.pack_forget()
        
        self.status_bar = tk.Label(self.root, text="", font=("Arial", 12), bg="black", fg="white", anchor="center")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.update_idletasks()
        self.get_box_centers()

    def setup_modality_dropdown(self):
        modality_frame = tk.Frame(self.root, bg="white")
        modality_frame.pack(pady=0)

        modality_label = tk.Label(modality_frame, text="Select Modality:", font=("Arial", 12), bg="white")
        modality_label.pack(side=tk.LEFT, padx=5)

        modality_dropdown = ttk.Combobox(modality_frame, textvariable=self.current_modality, 
                                         values=["Mouse Control", "Voice Control", "Eye Tracking"], 
                                         state="readonly", width=15)
        modality_dropdown.pack(side=tk.LEFT)
        modality_dropdown.bind("<<ComboboxSelected>>", self.change_modality)

    def setup_speech_recognition(self):
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

    def setup_eye_tracking(self):
        if self.eye_tracking_available:
            return

        try:
            found_eyetrackers = tr.find_all_eyetrackers()
            if len(found_eyetrackers) == 0:
                raise Exception("No eye trackers found")
            self.eye_tracker = found_eyetrackers[0]
            print(f"Found eye tracker: {self.eye_tracker.model}")
            self.eye_tracking_available = True
        except Exception as e:
            print(f"Warning! Eye tracker setup failed: {e}")
            self.eye_tracking_available = False

    def create_eye_gaze_pointer(self):
        if self.eye_tracking_available and not self.eye_gaze_pointer:
            self.eye_gaze_pointer = EyeGazePointer(self.root, self.eye_tracker)
            self.eye_gaze_pointer.withdraw()  # Hide initially

    def show_eye_gaze_pointer(self):
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.deiconify()

    def hide_eye_gaze_pointer(self):
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.withdraw()
            
    def get_button_center(self, button):
        x = button.winfo_x() + button.winfo_width() / 2 + 78
        y = button.winfo_y() + button.winfo_height() / 2 + 115
        
        parent = button.master
        while parent != self.floor_panel:
            x += parent.winfo_x()
            y += parent.winfo_y()
            parent = parent.master
        return x, y
    
    def get_box_centers(self):
        self.root.update_idletasks()
        self.coordinates = []

        for i, (button_frame, button) in enumerate(self.floor_buttons):
            x, y = self.get_button_center(button)
            self.coordinates.append([x, y])

        additional_buttons = [
            (self.open_button_frame, self.open_button),
            (self.close_button_frame, self.close_button),
            (self.emergency_button_frame, self.emergency_button)
        ]

        for button_frame, button in additional_buttons:
            x, y = self.get_button_center(button)
            self.coordinates.append([x, y])

        print("Coordinates:", self.coordinates)

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def recognize_speech_from_mic(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4096)
        self.stream.start_stream()
        print("Listening...")
        self.update_status("Listening...")
        self.show_listening_label()

        try:
            while not self.stop_processing:
                data = self.stream.read(4096, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    result = self.recognizer.Result()
                    self.recognizer.SetGrammar(json.dumps(self.grammar))
                    text = json.loads(result).get("text", "")
                    if text:
                        self.update_status("")
                        self.hide_listening_label()
                        return text
        except Exception as e:
            print(f"Error in speech recognition: {e}")
        finally:
            self.cleanup_audio()

    def cleanup_audio(self):
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'p') and self.p:
            self.p.terminate()

    def update_status(self, message):
        self.status_bar.config(text=message)
        self.root.update()

    def show_listening_label(self):
        self.listening_label.pack(side=tk.BOTTOM, pady=10)
        self.root.update()

    def hide_listening_label(self):
        self.listening_label.pack_forget()
        self.root.update()

    def update_arrow_direction(self, current_floor, target_floor):
        if current_floor < target_floor:
            self.arrow_label.config(text="↑")
        elif current_floor > target_floor:
            self.arrow_label.config(text="↓")
        else:
            self.arrow_label.config(text="  ")
    
    def reset_button_color_after_delay(self, button_frame):
        self.root.after(2000, lambda: button_frame.config(bg="white"))

    def open_door(self):
        self.door_status = "Open"
        self.door_status_label.config(text="Opened")
        self.open_button_frame.config(bg="green")
        self.reset_button_color_after_delay(self.open_button_frame)
        self.calculate_and_save_metrics(10, self.get_gaze_data())
        self.speak("Door opened")

    def close_door(self):
        self.door_status = "Closed"
        self.door_status_label.config(text="Closed")
        self.close_button_frame.config(bg="green")
        self.reset_button_color_after_delay(self.close_button_frame)
        self.calculate_and_save_metrics(11, self.get_gaze_data())
        self.speak("Door closed")

    def simulate_emergency(self):
        self.speak("Emergency button pressed. Elevator stopped.")
        self.emergency_button_frame.config(bg="red")
        self.calculate_and_save_metrics(12, self.get_gaze_data())
        self.emergency_triggered = True
        self.root.after(2000, self.close_application)  # Close after 2 seconds
        
    def close_application(self):
        self.stop()
        self.root.destroy()
        
    def handle_floor_button(self, target_floor):
        if self.elevator_moving:
            self.speak("Elevator is moving. Please wait.")
            return

        if self.door_status == "Open":
            self.speak("Please close the door first")
        else:
            if self.selected_floor is not None:
                prev_frame, _ = self.floor_buttons[self.selected_floor - 1]
                prev_frame.config(bg="white")

            button_frame, button = self.floor_buttons[target_floor - 1]
            button_frame.config(bg="green")
            self.selected_floor = target_floor
            self.move_elevator(target_floor)
            gaze_data = self.get_gaze_data()
            self.calculate_and_save_metrics(target_floor, gaze_data)

    def move_elevator(self, target_floor):
        if self.door_status == "Open":
            print("Please close the door first")
            self.speak("Please close the door first")
            return

        if target_floor == self.current_floor:
            self.update_status(f"Already at Floor {target_floor}")
            self.reset_button_color(target_floor)
            return

        self.elevator_moving = True
        direction = 1 if target_floor > self.current_floor else -1
        floors = range(self.current_floor, target_floor + direction, direction)

        for floor in floors:
            self.current_floor = floor
            self.floor_label.config(text=str(floor))
            self.slider.set(self.current_floor)
            self.update_arrow_direction(floor, target_floor)
            self.root.update()
            time.sleep(0.8)

        self.speak(f"Arrived at Floor {target_floor}")
        self.reset_button_color(target_floor)
        self.elevator_moving = False

    def reset_button_color(self, floor):
        button_frame, _ = self.floor_buttons[floor - 1]
        button_frame.config(bg="white")
        self.selected_floor = None

    def handle_voice_command(self):
        command = self.recognize_speech_from_mic()
        print(f"You said: {command}")
        self.process_voice_command(command)

    def change_modality(self, event=None):
        selected_modality = self.current_modality.get()
        self.stop_current_modality()

        if selected_modality == "Mouse Control":
            self.active_modality = "mouse"
            self.hide_eye_gaze_pointer()
            self.update_status("Mouse Control Active")
        elif selected_modality == "Voice Control":
            self.active_modality = "voice"
            self.hide_eye_gaze_pointer()
            self.start_voice_recognition()
        elif selected_modality == "Eye Tracking":
            if self.eye_tracking_available:
                self.active_modality = "eye"
                self.show_eye_gaze_pointer()
                self.start_eye_tracking()
            else:
                messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to Mouse Control.")
                self.current_modality.set("Mouse Control")
                self.active_modality = "mouse"
                self.update_status("Mouse Control Active")

    def stop_current_modality(self):
        self.stop_processing = True
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=1)
        if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
            self.eye_tracker_thread.join(timeout=1)
        self.cleanup_audio()
        self.hide_eye_gaze_pointer()
        self.stop_processing = False

    def start_voice_recognition(self):
        self.stop_processing = False
        self.voice_thread = threading.Thread(target=self._voice_recognition_loop)
        self.voice_thread.daemon = True
        self.voice_thread.start()
        self.update_status("Voice Control Active")

    def _voice_recognition_loop(self):
        while not self.stop_processing:
            try:
                command = self.recognize_speech_from_mic()
                print(f"You said: {command}")
                if self.emergency_triggered:
                    break
                self.process_voice_command(command)
            except Exception as e:
                print(f"Error in voice recognition loop: {e}")
                time.sleep(1)
            if self.emergency_triggered:
                break

    def start_eye_tracking(self):
        if not self.eye_tracking_available:
            messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to Mouse Control.")
            self.current_modality.set("Mouse Control")
            self.update_status("Mouse Control Active")
            return

        self.stop_processing = False
        self.eye_tracker_thread = threading.Thread(target=self._eye_tracking_loop)
        self.eye_tracker_thread.daemon = True
        self.eye_tracker_thread.start()
        self.update_status("Eye Tracking Active")

    def _eye_tracking_loop(self):
        dwell_time = 1.5
        threshold = 0.8

        while not self.stop_processing:
            try:
                weights = [0.0] * len(self.coordinates)
                start_time = time.time()

                while time.time() - start_time < dwell_time and not self.stop_processing:
                    gaze_point, selected = self.get_nearest_box()
                    if gaze_point is not None and selected is not None:
                        x, y = gaze_point
                        self.eye_tracking_queue.put(('update_pointer', (x, y)))
                        
                        elapsed_time = time.time() - start_time
                        progress = elapsed_time / dwell_time
                        color = self.get_color_gradient(progress)
                        
                        if selected < self.max_floors:
                            button_frame, _ = self.floor_buttons[selected]
                        elif selected == self.max_floors:
                            button_frame = self.open_button_frame
                        elif selected == self.max_floors + 1:
                            button_frame = self.close_button_frame
                        elif selected == self.max_floors + 2:
                            button_frame = self.emergency_button_frame
                        
                        self.eye_tracking_queue.put(('update_button_color', (button_frame, color)))
                        
                        weights[selected] += 0.1  # Increment by a small amount
                    else:
                        self.eye_tracking_queue.put(('hide_pointer', None))

                    time.sleep(0.1)

                # Reset button colors
                self.eye_tracking_queue.put(('reset_button_colors', None))

                max_weight = max(weights)
                if max_weight > 0 and (max_weight / sum(weights)) >= threshold:
                    selected = weights.index(max_weight)
                    print(f"Selected box: {selected}")
                    self.eye_tracking_queue.put(('handle_selection', selected))

                time.sleep(0.2)
            except Exception as e:
                print(f"Error in eye tracking loop: {e}")
                time.sleep(1)

    def get_color_gradient(self, progress):
        r = int(255 * (1 - progress))
        g = int(255 * progress)
        b = 0
        return f'#{r:02x}{g:02x}{b:02x}'

    def reset_button_colors(self):
        for button_frame, _ in self.floor_buttons:
            button_frame.config(bg="white")
        self.open_button_frame.config(bg="white")
        self.close_button_frame.config(bg="white")
        self.emergency_button_frame.config(bg="white")

    def handle_eye_tracking_selection(self, selected):
        if self.elevator_moving:
            self.speak("Elevator is moving. Please wait.")
            return

        gaze_data = self.get_gaze_data()

        if selected < self.max_floors:
            self.handle_floor_button(selected + 1)
            self.calculate_and_save_metrics(selected + 1, gaze_data)
        elif selected == self.max_floors:
            self.open_door()
        elif selected == self.max_floors + 1:
            self.close_door()
        elif selected == self.max_floors + 2:
            self.simulate_emergency()

    def get_nearest_box(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            return None, None

        try:
            gaze_data = {}
            def gaze_data_callback(gaze_data_):
                nonlocal gaze_data
                gaze_data = gaze_data_

            self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
            time.sleep(0.1)
            self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

            if gaze_data:
                left_eye = gaze_data.get('left_gaze_point_on_display_area', (0, 0))
                right_eye = gaze_data.get('right_gaze_point_on_display_area', (0, 0))
                x = (left_eye[0] + right_eye[0]) / 2
                y = (left_eye[1] + right_eye[1]) / 2 - 0.1

                print(f"Gaze point: ({x}, {y})")

                if x == 0 and y == 0:
                    return None, None

                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight() 
                x *= screen_width
                y *= screen_height

                distances = [np.sqrt((x - coord[0])**2 + (y - coord[1])**2) for coord in self.coordinates]
                nearest_box = np.argmin(distances)
                print(f"Nearest box: {nearest_box}")
                return (x, y), nearest_box
            else:
                print("No gaze data received")
                return None, None
        except Exception as e:
            print(f"Eye tracking error: {e}")
            return None, None

    def calculate_and_save_metrics(self, selected_floor, gaze_data):
        current_time = time.time()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time))
        self.command_count += 1

        total_time = max(current_time - self.start_time, 0.001)
        total_buttons = max(self.max_floors + 3, 1)
        itr_buttons = math.log2(total_buttons) * (self.command_count / total_time)
        ter = self.command_count / total_time
        frames = self.get_frame_count()

        meanx, meany, stdx, stdy = 0, 0, 0, 0
        meanlp, meanrp, stdlp, stdrp = 0, 0, 0, 0

        if gaze_data and len(gaze_data) > 1:
            gaze_points = np.array(gaze_data)
            xy_points = gaze_points[:, :2]  # Only take x and y coordinates
            
            # Convert to screen coordinates before calculating mean and std
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            xy_points[:, 0] *= screen_width
            xy_points[:, 1] *= screen_height
            
            meanx, meany = np.mean(xy_points, axis=0)
            stdx, stdy = np.std(xy_points, axis=0)          

            if gaze_points.shape[1] > 2:
                left_pupil = gaze_points[:, 2]
                right_pupil = gaze_points[:, 3]
                meanlp = np.mean(left_pupil)
                meanrp = np.mean(right_pupil)
                stdlp = np.std(left_pupil)
                stdrp = np.std(right_pupil)

        def safe_str_round(value, decimals=4):
            if np.isnan(value):
                return "0"
            return str(round(value, decimals))

        command_num = selected_floor
        if selected_floor == 10:  # Open door
            command_num = 10
        elif selected_floor == 11:  # Close door
            command_num = 11
        elif selected_floor == 12:  # Emergency
            command_num = 12

        self.all_data["Command"].append(str(command_num))
        self.all_data["Timestamp"].append(timestamp)
        self.all_data["Frames"].append(str(frames))
        self.all_data["TER"].append(safe_str_round(ter))
        self.all_data["ITRbuttons"].append(safe_str_round(itr_buttons))
        self.all_data["meanx"].append(safe_str_round(meanx))
        self.all_data["meany"].append(safe_str_round(meany))
        self.all_data["stdx"].append(safe_str_round(stdx))
        self.all_data["stdy"].append(safe_str_round(stdy))
        self.all_data["meanlp"].append(safe_str_round(meanlp))
        self.all_data["meanrp"].append(safe_str_round(meanrp))
        self.all_data["stdlp"].append(safe_str_round(stdlp))
        self.all_data["stdrp"].append(safe_str_round(stdrp))
        self.all_data["floor"].append(str(selected_floor))

    def get_frame_count(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            return 0

        frame_count = [0]
        def frame_callback(frame_data):
            frame_count[0] += 1

        self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, frame_callback, as_dictionary=True)
        time.sleep(1.5)
        self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, frame_callback)

        return frame_count[0]
    
    def get_gaze_data(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            return None

        gaze_data = []
        def gaze_data_callback(gaze_data_):
            nonlocal gaze_data
            left_eye = gaze_data_.get('left_gaze_point_on_display_area', (0, 0))
            right_eye = gaze_data_.get('right_gaze_point_on_display_area', (0, 0))
            x = (left_eye[0] + right_eye[0]) / 2
            y = (left_eye[1] + right_eye[1]) / 2 - 0.1
            left_pupil = gaze_data_.get('left_pupil_diameter', 0)
            right_pupil = gaze_data_.get('right_pupil_diameter', 0)
            gaze_data.append([x, y, left_pupil, right_pupil])

        self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
        time.sleep(1.5)
        self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

        return gaze_data if gaze_data else None
    
    def process_eye_tracking_queue(self):
        try:
            while not self.eye_tracking_queue.empty():
                action, data = self.eye_tracking_queue.get_nowait()
                if action == 'update_pointer':
                    self.update_eye_gaze_pointer(*data)
                elif action == 'update_button_color':
                    button_frame, color = data
                    button_frame.config(bg=color)
                elif action == 'hide_pointer':
                    self.hide_eye_gaze_pointer()
                elif action == 'reset_button_colors':
                    self.reset_button_colors()
                elif action == 'handle_selection':
                    self.handle_eye_tracking_selection(data)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_eye_tracking_queue)
    
    def process_voice_command(self, command):
        target_floor = 0
        try:
            for word, number in self.number_map.items():
                if word in command:
                    target_floor = number
                    break
            if "open" in command:
                self.open_door()
            elif "close" in command:
                self.close_door()
            elif "emergency" in command:
                self.simulate_emergency()
            elif target_floor > 0:
                if target_floor > self.max_floors or target_floor < 1:
                    self.speak("Invalid floor number")
                elif self.elevator_moving:
                    self.speak("Elevator is moving. Please wait.")
                else:
                    self.handle_floor_button(target_floor)
        except Exception as e:
            print(e)

    def save_metrics_to_file(self, filename="Lift Interface/data_collected/elevator_metrics_3.csv"):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.all_data.keys())
            for i in range(len(self.all_data["Command"])):
                writer.writerow([self.all_data[key][i] for key in self.all_data.keys()])

    def stop(self):
        self.stop_processing = True
        self.emergency_triggered = True
        self.save_metrics_to_file()
        
        # Stop voice recognition thread
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=2)
        
        # Stop eye tracking thread
        if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
            self.eye_tracker_thread.join(timeout=2)
        
        # Clean up audio resources
        self.cleanup_audio()
        
        # Close eye gaze pointer
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.close()

    def update_eye_gaze_pointer(self, x, y):
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.geometry(f"20x20+{int(x)}+{int(y)}")
            
    def update_ui(self):
        self.root.update_idletasks()
        self.root.after(10, self.update_ui)

    def run(self):
        self.setup_eye_tracking()
        self.create_eye_gaze_pointer()
        self.change_modality()
        self.root.protocol("WM_DELETE_WINDOW", self.close_application)
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"Error in main loop: {e}")
            self.close_application()

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevatorApp(root)
    app.run()