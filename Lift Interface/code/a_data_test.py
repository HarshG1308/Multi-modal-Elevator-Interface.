import csv
import json
import math
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
import pyaudio
import pyttsx3
import tobii_research as tr
from vosk import KaldiRecognizer, Model


class ElevatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice-Activated Elevator Interface")
        self.root.geometry("800x600")
        self.root.configure(bg="white")
        self.all_plus_plus_active = False

        self.max_floors = 9
        self.coordinates = []
        self.current_floor = 1
        self.door_status = "Closed"
        self.stop_processing = False
        self.slider = None
        self.selected_floor = None
        self.elevator_moving = False
        
        self.open_button_frame = None
        self.close_button_frame = None
        self.emergency_button_frame = None
        self.open_button = None
        self.close_button = None
        self.emergency_button = None

        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)

        self.current_modality = tk.StringVar()
        self.current_modality.set("Mouse Control")

        self.eye_tracker = None
        self.eye_tracking_available = False

        self.speech_queue = queue.Queue()
        self.speech_thread = None
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
        self.setup_eye_tracking()

    def setup_gui(self):
        # Header
        heading_label = tk.Label(self.root, text="Multi-Modal Elevator Interface", font=("Arial", 24, "bold"), bg="white", fg="black")
        heading_label.pack(pady=5)

        self.setup_modality_dropdown()

        # Main panel frame
        panel_frame = tk.Frame(self.root, bg="white")
        panel_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)   

        # Floor panel
        self.floor_panel = tk.Frame(panel_frame, bg="white", padx=20, pady=20, bd=5, relief=tk.SUNKEN)
        self.floor_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        floor_panel_label = tk.Label(self.floor_panel, text="Floor Panel", font=("Arial", 16, "bold"), bg="white", fg="black")
        floor_panel_label.pack(pady=10)

        # Floor buttons
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

        # Additional buttons
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

        # Elevator panel
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

        # Door status label
        door_label = tk.Label(elevator_panel, text="Door: ", font=("Arial", 16), bg="white", fg="black")
        door_label.pack(pady=10, side=tk.LEFT, padx=10)

        self.door_status_label = tk.Label(elevator_panel, text=self.door_status, font=("Arial", 16), bg="white")
        self.door_status_label.pack(pady=10, side=tk.LEFT, padx=10)
        
        # Listening label
        self.listening_label = tk.Label(self.root, text="Listening...", font=("Arial", 16), bg="white", fg="black")
        self.listening_label.pack(side=tk.BOTTOM, pady=10)
        self.listening_label.pack_forget()  # Initially hide the label
        
        # Status bar
        self.status_bar = tk.Label(self.root, text="", font=("Arial", 12), bg="black", fg="white", anchor="center")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Gaze canvas
        self.gaze_canvas = tk.Canvas(self.root, width=self.root.winfo_screenwidth(), height=self.root.winfo_screenheight(), bg="white")
        self.gaze_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.root.update_idletasks()  # Force update of widget positions
        self.get_box_centers()

    def setup_modality_dropdown(self):
        modality_frame = tk.Frame(self.root, bg="white")
        modality_frame.pack(pady=0)

        modality_label = tk.Label(modality_frame, text="Select Modality:", font=("Arial", 12), bg="white")
        modality_label.pack(side=tk.LEFT, padx=5)

        modality_dropdown = ttk.Combobox(modality_frame, textvariable=self.current_modality, 
                                 values=["Voice Control", "Eye Tracking", "Mouse Control", "Touch Control", "ALL", "ALL++"], 
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
                "open door", "close door", "emergency",
                "first", "second", "third", "fourth", "fifth",
                "sixth", "seventh", "eighth", "ninth", "tenth"
            ]
        }

        model = Model(model_path)
        self.recognizer = KaldiRecognizer(model, 16000, json.dumps(self.grammar))

        self.number_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
            "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
        }

    def setup_eye_tracking(self):
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

    def get_button_center(self, button):
        x = button.winfo_x() + button.winfo_width() / 2 + 78
        y = button.winfo_y() + button.winfo_height() / 2 + 115
        
        # Adjust for parent frame offset
        parent = button.master
        while parent != self.floor_panel:
            x += parent.winfo_x()
            y += parent.winfo_y()
            parent = parent.master
        
        return x, y

    def get_box_centers(self):
        self.root.update_idletasks()  # Force update of widget positions
        self.coordinates = []

        # Floor buttons
        for i, (button_frame, button) in enumerate(self.floor_buttons):
            x, y = self.get_button_center(button)
            self.coordinates.append([x, y])

        # Additional buttons
        additional_buttons = [
            (self.open_button_frame, self.open_button),
            (self.close_button_frame, self.close_button),
            (self.emergency_button_frame, self.emergency_button)
        ]

        for button_frame, button in additional_buttons:
            x, y = self.get_button_center(button)
            self.coordinates.append([x, y])

    def get_nearest_box(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            return None, None

        try:
            gaze_data = {}
            def gaze_data_callback(gaze_data_):
                nonlocal gaze_data
                gaze_data = gaze_data_

            self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
            time.sleep(0.5)  # Increased wait time
            self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

            if gaze_data:
                left_eye = gaze_data.get('left_gaze_point_on_display_area', (0, 0))
                right_eye = gaze_data.get('right_gaze_point_on_display_area', (0, 0))
                x = (left_eye[0] + right_eye[0]) / 2
                y = (left_eye[1] + right_eye[1]) / 2 - 0.1  # Adjust for offset

                # Convert from relative coordinates to screen coordinates
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight() 
                x *= screen_width
                y *= screen_height
                
                distances = [np.sqrt((x - coord[0])**2 + (y - coord[1])**2) for coord in self.coordinates]
                if np.isnan(distances).all() or np.isinf(distances).all() or not distances:
                    return None, None
                nearest_box = np.argmin(distances)
                print(f"Nearest box: {nearest_box + 1}")  # Debug print (add 1 for 1-based indexing)
                return (x, y), nearest_box + 1  # Return 1-based index
            else:
                print("No gaze data received")  # Debug print
                return None, None
        except Exception as e:
            print(f"Eye tracking error: {e}")
            return None, None

    def speak(self, text):
        self.speech_queue.put(text)
        if self.speech_thread is None or not self.speech_thread.is_alive():
            self.speech_thread = threading.Thread(target=self._speak_thread, daemon=True)
            self.speech_thread.start()

    def _speak_thread(self):
        while True:
            try:
                text = self.speech_queue.get(block=False)
                self.engine.say(text)
                self.engine.runAndWait()
                self.speech_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error in speech thread: {e}")
                break
        
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
        self.root.update

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
        self.root.after(4000, lambda: button_frame.config(bg="white"))

    def open_door(self):
        self.door_status = "Open"
        self.door_status_label.config(text="Opened")
        self.open_button_frame.config(bg="#00FF00")
        self.reset_button_color_after_delay(self.open_button_frame)
        self.calculate_and_save_metrics(10, self.get_gaze_data())
        self.speak("Door opened")

    def close_door(self):
        self.door_status = "Closed"
        self.door_status_label.config(text="Closed")
        self.close_button_frame.config(bg="#00FF00")
        self.reset_button_color_after_delay(self.close_button_frame)
        self.calculate_and_save_metrics(11, self.get_gaze_data())
        self.speak("Door closed")

    def simulate_emergency(self):
        self.emergency_button_frame.config(bg="red")
        self.speak("Emergency button pressed. Elevator stopped.")
        self.calculate_and_save_metrics(12, self.get_gaze_data())
        root.quit()

    def handle_floor_button(self, target_floor):
        if self.all_plus_plus_active:
            self.handle_floor_button_all_plus_plus(target_floor)
        if self.elevator_moving:
            self.speak("Elevator is moving. Please wait.")
            return

        if self.door_status == "Open":
            self.speak("Please close the door first")
        else:
            # Reset previous selection if any
            if self.selected_floor is not None:
                prev_frame, _ = self.floor_buttons[self.selected_floor - 1]
                prev_frame.config(bg="white")

            button_frame, button = self.floor_buttons[target_floor - 1]
            button_frame.config(bg="#00FF00")
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
            
    def stop_current_modality(self):
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=1)
        if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
            self.eye_tracker_thread.join(timeout=1)
        self.stop_processing = True

    def change_modality(self, event=None):
        selected_modality = self.current_modality.get()
        self.stop_current_modality()
            
        if selected_modality == "Mouse Control":
            self.update_status("Mouse Control Active")
            # stop voice recognition if running
            if self.voice_thread and self.voice_thread.is_alive():
                self.voice_thread.join(timeout=1)
            # stop eye tracking if running
            if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
                self.eye_tracker_thread.join(timeout=1)
            return
        elif selected_modality == "Voice Control":
            # stop eye tracking if running
            if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
                self.eye_tracker_thread.join(timeout=1)
            self.setup_speech_recognition()
            self.start_voice_recognition()
        elif selected_modality == "Eye Tracking":
            # stop voice recognition if running
            if self.voice_thread and self.voice_thread.is_alive():
                self.voice_thread.join(timeout=1)
            if self.eye_tracking_available:
                self.start_eye_tracking()
            else:
                messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to MOUSE Control.")
                self.current_modality.set("Mouse Control")
        elif selected_modality == "Touch Control":
            return
        elif selected_modality == "ALL":
            self.setup_speech_recognition()
            self.start_voice_recognition()
            if self.eye_tracking_available:
                self.start_eye_tracking()      
        elif selected_modality == "ALL++":
            self.setup_speech_recognition()
            self.update_status("ALL++ Mode Active")
            self.handle_all_plus_plus()      
    
    def handle_all_plus_plus(self):
        collection_time = 15  # Time to collect commands in seconds
        commands = []
        start_time = time.time()

        self.speak("ALL++ mode activated. Please select floors using any input method.")
        self.update_status("ALL++ Mode: Select floors (15 seconds)")
        self.show_command_collection_indicator(True)

        # Start threads for different input methods
        voice_thread = threading.Thread(target=self.collect_voice_commands, args=(commands, start_time, collection_time))
        eye_tracking_thread = threading.Thread(target=self.collect_eye_tracking_commands, args=(commands, start_time, collection_time))
        
        voice_thread.start()
        eye_tracking_thread.start()

        # Collect mouse/touch inputs in the main thread
        while time.time() - start_time < collection_time:
            self.root.update()
            time.sleep(0.1)

        voice_thread.join()
        eye_tracking_thread.join()

        self.show_command_collection_indicator(False)

        if not commands:
            self.speak("No valid commands received.")
            return

        self.speak("Processing commands.")
        self.update_status("Processing commands...")

        # Sort commands and remove duplicates
        unique_commands = sorted(set(commands))

        # Execute commands
        for floor in unique_commands:
            self.handle_floor_button(floor)
            while self.elevator_moving:
                time.sleep(0.5)

        self.speak("All commands executed.")
        self.update_status("All commands executed.")

    def show_command_collection_indicator(self, show):
        if show:
            self.collection_indicator = tk.Label(self.root, text="Collecting Commands", bg="yellow", fg="black", font=("Arial", 16))
            self.collection_indicator.pack(side=tk.TOP, fill=tk.X)
        else:
            if hasattr(self, 'collection_indicator'):
                self.collection_indicator.destroy()

    def collect_voice_commands(self, commands, start_time, collection_time):
        while time.time() - start_time < collection_time:
            command = self.recognize_speech_from_mic()
            if command:
                floor = self.extract_floor_from_command(command)
                if floor:
                    commands.append(floor)
                    self.speak(f"Added floor {floor} to the queue.")

    def collect_eye_tracking_commands(self, commands, start_time, collection_time):
        if not self.eye_tracking_available:
            return

        while time.time() - start_time < collection_time:
            _, selected = self.get_nearest_box()
            if selected and 1 <= selected <= self.max_floors:
                commands.append(selected)
                self.speak(f"Added floor {selected} to the queue.")
            time.sleep(0.5)  # Add a small delay to prevent too frequent checks

    def handle_floor_button_all_plus_plus(self, floor):
        if 1 <= floor <= self.max_floors:
            self.selected_floor = floor
            button_frame, _ = self.floor_buttons[floor - 1]
            button_frame.config(bg="#00FF00")
            self.speak(f"Added floor {floor} to the queue.")
            self.root.after(1000, lambda: button_frame.config(bg="white"))

    def extract_floor_from_command(self, command):
        for word, number in self.number_map.items():
            if word in command:
                return number
        return None

    def start_voice_recognition(self):
        self.stop_processing = False
        self.voice_thread = threading.Thread(target=self._voice_recognition_loop)
        self.voice_thread.daemon = True
        self.voice_thread.start()
        self.update_status("Voice Control Active")

    def _voice_recognition_loop(self):
        while not self.stop_processing:
            try:
                self.handle_voice_command()
            except Exception as e:
                print(f"Error in voice recognition loop: {e}")
                time.sleep(1)

    def start_eye_tracking(self):
        if not self.eye_tracking_available:
            messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to Voice Control.")
            self.current_modality.set("Mouse Control")
            return

        self.stop_processing = False
        self.eye_tracker_thread = threading.Thread(target=self._eye_tracking_loop)
        self.eye_tracker_thread.daemon = True
        self.eye_tracker_thread.start()
        self.update_status("Eye Tracking Active")
        
    def update_button_color(self, selected, progress):
        for i, (button_frame, _) in enumerate(self.floor_buttons):
            if i == selected:
                # Create a smooth gradient from white to green
                r = int(255 * (1 - progress))
                g = 255
                b = int(255 * (1 - progress))
                color = f'#{r:02x}{g:02x}{b:02x}'
                button_frame.config(bg=color)
            else:
                button_frame.config(bg="white")
        
        # Handle additional buttons
        additional_buttons = [self.open_button_frame, self.close_button_frame, self.emergency_button_frame]
        for i, button_frame in enumerate(additional_buttons):
            if i + self.max_floors == selected:
                r = int(255 * (1 - progress))
                g = 255
                b = int(255 * (1 - progress))
                color = f'#{r:02x}{g:02x}{b:02x}'
                button_frame.config(bg=color)
            else:
                button_frame.config(bg="white")

    def _eye_tracking_loop(self):
        dwell_time = 3.0
        threshold = 0.8

        while not self.stop_processing:
            try:
                if self.elevator_moving:
                    self.root.after(0, self.update_status, f"Moving to floor {self.selected_floor}")
                    time.sleep(0.5)
                    continue

                weights = [0.0] * (len(self.coordinates) + 1)  # Add one extra for 1-based indexing
                start_time = time.time()
                last_selected = None

                while time.time() - start_time < dwell_time and not self.stop_processing and not self.elevator_moving:
                    gaze_point, selected = self.get_nearest_box()
                    if gaze_point is not None and selected is not None:
                        elapsed = time.time() - start_time
                        weights[selected] += elapsed - sum(weights)
                        progress = min(weights[selected] / dwell_time, 1.0)
                        
                        self.root.after(0, self.update_button_color, selected - 1, progress)  # Adjust for 0-based indexing
                        self.root.after(0, self.display_gaze_point, gaze_point)
                        
                        if selected != last_selected:
                            # self.speak(f"Looking at {selected}")
                            last_selected = selected

                    time.sleep(0.05)  # Small delay to reduce CPU usage

                if self.elevator_moving:
                    continue

                max_weight = max(weights)
                if max_weight > 0 and (max_weight / sum(weights)) >= threshold:
                    selected = weights.index(max_weight)
                    print(f"Selected box: {selected}")  # Debug print
                    gaze_data = self.get_gaze_data()
                    if gaze_data:
                        self.root.after(0, self.handle_eye_tracking_selection, selected)
                        self.calculate_and_save_metrics(selected, gaze_data)
                    else:
                        print("No gaze data available")

                # Reset all button colors
                self.root.after(0, self.update_button_color, -1, 0)

                time.sleep(0.2)  # Short delay before starting the next selection cycle
            except Exception as e:
                print(f"Error in eye tracking loop: {e}")
                time.sleep(1)  # Wait a bit before trying again

    def handle_eye_tracking_selection(self, selected):
        if self.elevator_moving:
            self.speak("Elevator is moving. Please wait.")
            return

        gaze_data = self.get_gaze_data()

        if selected < self.max_floors + 1:
            self.handle_floor_button(selected)
            self.calculate_and_save_metrics(selected, gaze_data)
        elif selected == self.max_floors + 1:
            self.open_door()
            self.calculate_and_save_metrics("Open", gaze_data)
        elif selected == self.max_floors + 2:
            self.close_door()
            self.calculate_and_save_metrics("Close", gaze_data)
        elif selected == self.max_floors + 3:
            self.simulate_emergency()
            self.calculate_and_save_metrics("Emergency", gaze_data)

    def display_gaze_point(self, point):
        x, y = point
        self.gaze_canvas.create_oval(x-5, y-5, x+5, y+5, fill="red", tags="gaze_point")
        self.gaze_canvas.after(100, self.gaze_canvas.delete, "gaze_point")
        


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
            if np.isnan(value) or np.isinf(value):
                return "0.0"
            return str(round(float(value), decimals))

        command_num = selected_floor
        if selected_floor == "Open":  # Open door
            command_num = 10
        elif selected_floor == "Close":  # Close door
            command_num = 11
        elif selected_floor == "Emergency":  # Emergency
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

        # Save metrics after each calculation
        self.save_metrics_to_file()

    def save_metrics_to_file(self, filename="Lift Interface\data_collected\elevator_metrics.csv"):
        if not any(self.all_data.values()):
            print("No data to save.")
            return

        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(self.all_data.keys())
                for i in range(len(self.all_data["Command"])):
                    row = [self.all_data[key][i] for key in self.all_data.keys()]
                    writer.writerow(row)
            print(f"Data saved successfully to {filename}")
        except Exception as e:
            print(f"Error saving data to file: {e}")

    def get_frame_count(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            return 0

        frame_count = [0]
        def frame_callback(frame_data):
            frame_count[0] += 1

        self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, frame_callback, as_dictionary=True)
        time.sleep(1.5)  # Collect data for 1.5 seconds
        self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, frame_callback)

        return frame_count[0]

    def get_gaze_data(self):
        if not self.eye_tracker or not self.eye_tracking_available:
            print("Eye tracker not available")
            return []

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
        time.sleep(1.5) # Collect data for 1.5 seconds
        self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)
        return gaze_data if gaze_data else []

    def stop(self):
        self.stop_processing = True
        self.save_metrics_to_file()
        self.stop_current_modality()
        
        # Clear the speech queue and wait for the speech thread to finish
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get(block=False)
                self.speech_queue.task_done()
            except queue.Empty:
                pass
        if self.speech_thread and self.speech_thread.is_alive():
            self.speech_thread.join(timeout=1)
        
        self.root.quit()

    def run(self): 
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"Error in main loop: {e}")
            self.stop()

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevatorApp(root)
    app.run()