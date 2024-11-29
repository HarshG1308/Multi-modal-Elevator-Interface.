import json
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import tobii_research as tr
import numpy as np
import pyaudio
import pyttsx3
from pytribe import EyeTribe
from vosk import KaldiRecognizer, Model

class ElevatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice-Activated Elevator Interface")
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
        
        self.open_button_frame = None
        self.close_button_frame = None
        self.emergency_button_frame = None
        self.open_button = None
        self.close_button = None
        self.emergency_button = None

        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)

        self.current_modality = tk.StringVar()
        self.current_modality.set("Voice Control")

        self.eye_tracker = None
        self.eye_tracking_available = False

        self.voice_thread = None
        self.eye_tracker_thread = None

        self.setup_gui()
        self.setup_speech_recognition()
        self.setup_eye_tracking()

    def setup_gui(self):
        # Header
        heading_label = tk.Label(self.root, text="Voice-Activated Elevator Interface", font=("Arial", 24, "bold"), bg="white", fg="black")
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
        
        # Outer interface setup
        self.setup_outer_interface()

        # Gaze canvas
        self.gaze_canvas = tk.Canvas(self.root, width=800, height=600, bg="white")
        self.gaze_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.root.update_idletasks()  # Force update of widget positions
        self.get_box_centers()

    def setup_modality_dropdown(self):
        modality_frame = tk.Frame(self.root, bg="white")
        modality_frame.pack(pady=0)

        modality_label = tk.Label(modality_frame, text="Select Modality:", font=("Arial", 12), bg="white")
        modality_label.pack(side=tk.LEFT, padx=5)

        modality_dropdown = ttk.Combobox(modality_frame, textvariable=self.current_modality, 
                                         values=["Voice Control", "Eye Tracking"], 
                                         state="readonly", width=15)
        modality_dropdown.pack(side=tk.LEFT)
        modality_dropdown.bind("<<ComboboxSelected>>", self.change_modality)

    def setup_outer_interface(self):
        self.outer_root = tk.Toplevel(self.root)
        self.outer_root.title("Elevator Outer Interface")
        self.outer_root.geometry("400x600")
        self.outer_root.configure(bg="white")

        # Header
        header_frame = tk.Frame(self.outer_root, bg="white")
        header_frame.pack(pady=10)

        header_label = tk.Label(header_frame, text="Elevator Outer Interface", font=("Arial", 20, "bold"), fg="black", bg="white")
        header_label.pack()

        # Floor display
        floor_display_frame = tk.Frame(self.outer_root, bg="white")
        floor_display_frame.pack(pady=10)

        self.outer_floor_label = tk.Label(floor_display_frame, text=f"Floor: {self.current_floor}", font=("Arial", 24), bg="white", fg="black")
        self.outer_floor_label.pack(side=tk.LEFT, padx=10)

        self.outer_direction_label = tk.Label(floor_display_frame, text="", font=("Arial", 24), bg="white", fg="black")
        self.outer_direction_label.pack(side=tk.LEFT, padx=10)

        # Canvas and elevator position
        canvas_frame = tk.Frame(self.outer_root, bg="white")
        canvas_frame.pack(pady=10)

        canvas_width = 300
        canvas_height = 500

        self.outer_canvas = tk.Canvas(canvas_frame, width=canvas_width, height=canvas_height, bg="white", highlightthickness=0)
        self.outer_canvas.pack(side=tk.LEFT, padx=10)

        # Elevator rectangle
        self.elevator_rect = self.outer_canvas.create_rectangle(10, 10, canvas_width - 10, 60, fill="black", outline="black")

        # Floor numbers
        floor_numbers_frame = tk.Frame(canvas_frame, bg="white")
        floor_numbers_frame.pack(side=tk.RIGHT, padx=10, fill=tk.Y)

        floor_height = canvas_height / self.max_floors
        for floor in range(self.max_floors, 0, -1):
            y = canvas_height - (floor * floor_height)
            floor_label = tk.Label(floor_numbers_frame, text=f"{floor}", font=("Arial", 16), fg="black", padx=10, pady=8)
            floor_label.pack(pady=5)

        # Footer
        footer_frame = tk.Frame(self.outer_root, bg="white")
        footer_frame.pack(pady=10, fill=tk.X)

        footer_label = tk.Label(footer_frame, text="© 2023 Elevator Co.", font=("Arial", 12), fg="black", bg="white")
        footer_label.pack()

    def setup_speech_recognition(self):
        model_path = r"Lift Interface\vosk-model-en-in-0.5"

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

        # Place the points on the buttons
        for i, (x, y) in enumerate(self.coordinates):
            point = tk.Label(self.floor_panel, text="O", font=("Arial", 10), bg="red", fg="white")
            point.place(x=x, y=y, anchor="center")
        
        print("Coordinates:", self.coordinates)

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

                print(f"Gaze point: ({x}, {y})")  # Debug print

                if x == 0 and y == 0:
                    return None, None

                # Convert from relative coordinates to screen coordinates
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight() 
                x *= screen_width
                y *= screen_height

                distances = [np.sqrt((x - coord[0])**2 + (y - coord[1])**2) for coord in self.coordinates]
                nearest_box = np.argmin(distances)
                print(f"Nearest box: {nearest_box}")  # Debug print
                return (x, y), nearest_box # Adjust for additional buttons
            else:
                print("No gaze data received")  # Debug print
                return None, None
        except Exception as e:
            print(f"Eye tracking error: {e}")
            return None, None

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

    def update_outer_direction(self, current_floor, target_floor, label):
        if current_floor < target_floor:
            label.config(text="↑")
        elif current_floor > target_floor:
            label.config(text="↓")
        else:
            label.config(text="")

    def update_elevator_position(self, floor):
        canvas_height = self.outer_canvas.winfo_height()
        floor_height = canvas_height / self.max_floors
        y = canvas_height - (floor * floor_height)
        self.outer_canvas.coords(self.elevator_rect, 10, y, self.outer_canvas.winfo_width() - 10, y + 50)

    def open_door(self):
        self.door_status = "Open"
        self.door_status_label.config(text="Opened")
        self.speak("Door opened")
        self.open_button_frame.config(bg="green").root.after(100, lambda: self.open_button_frame.config(bg="white"))

    def close_door(self):
        self.door_status = "Closed"
        self.door_status_label.config(text="Closed")
        self.speak("Door closed")

    def handle_floor_button(self, target_floor):
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
            button_frame.config(bg="green")
            self.selected_floor = target_floor
            self.move_elevator(target_floor)

    def move_elevator(self, target_floor):
        if self.door_status == "Open":
            print("Please close the door first")
            self.speak("Please close the door first")
            return

        if target_floor == self.current_floor:
            # self.speak(f"Already at Floor {target_floor}")
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

            # Update outer interface
            self.outer_floor_label.config(text=f"Floor: {floor}")
            self.update_outer_direction(floor, target_floor, self.outer_direction_label)
            self.update_elevator_position(floor)

            self.root.update()
            self.outer_root.update()
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
        target_floor = 0
        try:
            for word, number in self.number_map.items():
                if word in command:
                    target_floor = number
                    break
            if target_floor > self.max_floors or target_floor < 1:
                self.speak("Invalid floor number")
            elif target_floor == 0:
                if "open" in command:
                    self.open_door()
                elif "close" in command:
                    self.close_door()
                elif "emergency" in command:
                    self.simulate_emergency()
            else:
                if self.elevator_moving:
                    self.speak("Elevator is moving. Please wait.")
                else:
                    self.handle_floor_button(target_floor)
        except Exception as e:
            print(e)

    def simulate_emergency(self):
        self.speak("Emergency button pressed. Elevator stopped.")
        self.stop()

    def change_modality(self, event=None):
        selected_modality = self.current_modality.get()
        self.stop_current_modality()

        if selected_modality == "Voice Control":
            self.setup_speech_recognition()
            self.start_voice_recognition()
        elif selected_modality == "Eye Tracking":
            if self.eye_tracking_available:
                self.start_eye_tracking()
            else:
                messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to Voice Control.")
                self.current_modality.set("Voice Control")
                self.setup_speech_recognition()
                self.start_voice_recognition()

    def stop_current_modality(self):
        self.stop_processing = True
        if self.voice_thread and self.voice_thread.is_alive():
            self.voice_thread.join(timeout=1)
        if self.eye_tracker_thread and self.eye_tracker_thread.is_alive():
            self.eye_tracker_thread.join(timeout=1)
        self.cleanup_audio()

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
            self.current_modality.set("Voice Control")
            self.start_voice_recognition()
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
                        weights[selected] += time.time() - start_time
                        self.root.after(0, self.display_gaze_point, gaze_point)

                    time.sleep(0.1)  # Small delay to reduce CPU usage

                max_weight = max(weights)
                if max_weight > 0 and (max_weight / sum(weights)) >= threshold:
                    selected = weights.index(max_weight)
                    print(f"Selected box: {selected}")  # Debug print
                    self.root.after(0, self.handle_eye_tracking_selection, selected)

                time.sleep(0.2)  # Reduced delay between checks
            except Exception as e:
                print(f"Error in eye tracking loop: {e}")
                time.sleep(1)  # Wait a bit before trying again

    def display_gaze_point(self, point):
        x, y = point
        self.gaze_canvas.create_oval(x-5, y-5, x+5, y+5, fill="red", tags="gaze_point")
        self.gaze_canvas.after(100, self.gaze_canvas.delete, "gaze_point")

    def handle_eye_tracking_selection(self, selected):
        if self.elevator_moving:
            self.speak("Elevator is moving. Please wait.")
            return

        if selected < self.max_floors:
            self.handle_floor_button(selected + 1)
        elif selected == self.max_floors:
            self.open_door()
        elif selected == self.max_floors + 1:
            self.close_door()
        elif selected == self.max_floors + 2:
            self.simulate_emergency()

    def stop(self):
        self.stop_processing = True
        self.stop_current_modality()
        self.root.quit()
        self.outer_root.quit()

    def run(self):
        self.change_modality()  # Start the initial modality
        
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        self.outer_root.protocol("WM_DELETE_WINDOW", self.stop)
        
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"Error in main loop: {e}")
            self.stop()

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevatorApp(root)
    app.run()