import tkinter as tk
from tkinter import messagebox, ttk
import time
import threading
import math
import csv
import numpy as np
from eye_gaze_pointer import EyeGazePointer
from speech_recognition import SpeechRecognition
from eye_tracking import EyeTracking
import pyttsx3

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
        
        self.open_button_frame = None
        self.close_button_frame = None
        self.emergency_button_frame = None
        self.open_button = None
        self.close_button = None
        self.emergency_button = None
        self.eye_gaze_pointer = None
        
        self.active_modalities = set()

        self.current_modality = tk.StringVar()
        self.current_modality.set("Mouse Control")

        self.eye_tracker = None
        self.eye_tracking_available = False
        self.track_box = None

        self.voice_recognition = None
        self.eye_tracking = None
        
        self.start_time = time.time()
        self.command_count = 0
        self.all_data = {
            "Command": [], "Timestamp": [], "Frames": [], "TER": [], "ITRbuttons": [],
            "meanx": [], "meany": [], "stdx": [], "stdy": [],
            "meanlp": [], "meanrp": [], "stdlp": [], "stdrp": [], "floor": []
        }
        self.last_command_time = time.time()

        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)

        self.setup_gui()
        self.setup_speech_recognition()
        self.setup_eye_tracking()

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
                                         values=["Mouse Control", "Voice Control", "Eye Tracking", "ALL"], 
                                         state="readonly", width=15)
        modality_dropdown.pack(side=tk.LEFT)
        modality_dropdown.bind("<<ComboboxSelected>>", self.change_modality)

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

    def open_door(self):
        self.door_status = "Open"
        self.door_status_label.config(text="Opened")
        self.calculate_and_save_metrics(self.max_floors + 1, self.eye_tracking.get_gaze_data() if self.eye_tracking else None)
        self.speak("Door opened")    

    def close_door(self):
        self.door_status = "Closed"
        self.door_status_label.config(text="Closed")
        self.calculate_and_save_metrics(self.max_floors + 2, self.eye_tracking.get_gaze_data() if self.eye_tracking else None)
        self.speak("Door closed")
        self.close_button_frame.config(bg="green")
        
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

            if target_floor <= self.max_floors:
                button_frame, button = self.floor_buttons[target_floor - 1]
            elif target_floor == self.max_floors + 1:
                button_frame = self.open_button_frame
            elif target_floor == self.max_floors + 2:
                button_frame = self.close_button_frame
            elif target_floor == self.max_floors + 3:
                button_frame = self.emergency_button_frame

            button_frame.config(bg="green")
            self.selected_floor = target_floor
            self.move_elevator(target_floor)
            gaze_data = self.eye_tracking.get_gaze_data() if self.eye_tracking else None
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
        if floor <= self.max_floors:
            button_frame, _ = self.floor_buttons[floor - 1]
            button_frame.config(bg="white")
        elif floor == self.max_floors + 1:
            self.open_button_frame.config(bg="white")
        elif floor == self.max_floors + 2:
            self.close_button_frame.config(bg="white")
        elif floor == self.max_floors + 3:
            self.emergency_button_frame.config(bg="white")
        self.selected_floor = None

    def simulate_emergency(self):
        self.speak("Emergency button pressed. Elevator stopped.")
        self.emergency_button_frame.config(bg="red")
        self.calculate_and_save_metrics(self.max_floors + 3, self.eye_tracking.get_gaze_data() if self.eye_tracking else None)
        self.stop()
        
    def start_voice(self):
        self.voice_recognition.start()
        self.update_status("Listening...")

    def change_modality(self, event=None):
        selected_modality = self.current_modality.get()
        self.stop_current_modality()
        self.active_modalities.clear()

        if selected_modality == "Mouse Control":
            self.active_modalities.add("mouse")
            if self.eye_gaze_pointer:
                self.eye_gaze_pointer.hide()
            self.update_status("Mouse Control Active")
        elif selected_modality == "Voice Control":
            self.active_modalities.add("voice")
            if self.eye_gaze_pointer:
                self.eye_gaze_pointer.hide()
            self.start_voice()
        elif selected_modality == "Eye Tracking":
            if self.eye_tracking_available:
                self.active_modalities.add("eye")
                self.eye_gaze_pointer.show()
                self.start_eye_tracking()
            else:
                messagebox.showwarning("Eye Tracking Unavailable", "Eye tracking is not available. Falling back to Mouse Control.")
                self.current_modality.set("Mouse Control")
                self.active_modalities.add("mouse")
                self.update_status("Mouse Control Active")
        elif selected_modality == "ALL":
            self.active_modalities.update(["mouse", "voice", "eye"])
            self.start_voice_recognition()
            if self.eye_tracking_available:
                self.eye_gaze_pointer.show()
                self.start_eye_tracking()
            self.update_status("All Modalities Active")

    def setup_speech_recognition(self):
        self.voice_recognition = SpeechRecognition(self)

    def setup_eye_tracking(self):
        self.eye_tracking = EyeTracking(self)
        self.eye_tracking_available = self.eye_tracking.available
        if self.eye_tracking_available:
            self.eye_gaze_pointer = EyeGazePointer(self.root, self.eye_tracking.eye_tracker)
            self.eye_gaze_pointer.hide()

    def start_voice_recognition(self):
        if not self.voice_recognition.is_running():
            self.voice_recognition.start()
        self.update_status("Voice Control Active")

    def start_eye_tracking(self):
        if not self.eye_tracking.is_running():
            self.eye_tracking.start()
        self.update_status("Eye Tracking Active")

    def stop_current_modality(self):
        if self.voice_recognition:
            self.voice_recognition.stop()
        if self.eye_tracking:
            self.eye_tracking.stop()
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.hide()

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
            xy_points = gaze_points[:, :2]
            meanx, meany = np.mean(xy_points, axis=0)
            stdx, stdy = np.std(xy_points, axis=0)

            # Convert normalized coordinates to screen coordinates
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            meanx *= screen_width
            meany *= screen_height

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

        self.all_data["Command"].append(str(selected_floor))
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
        if not self.eye_tracking or not self.eye_tracking.available:
            return 0
        return self.eye_tracking.get_frame_count()

    def save_metrics_to_file(self, filename="Lift Interface/data_collected/elevator_metrics_3.csv"):
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(self.all_data.keys())
            for i in range(len(self.all_data["Command"])):
                writer.writerow([self.all_data[key][i] for key in self.all_data.keys()])

    def stop(self):
        self.stop_processing = True
        self.save_metrics_to_file()
        self.stop_current_modality()
        if self.eye_gaze_pointer:
            self.eye_gaze_pointer.close()
        self.root.quit()

    def update_ui(self):
        self.root.update_idletasks()
        self.root.after(10, self.update_ui)

    def run(self):
        self.setup_eye_tracking()
        self.change_modality()
        self.root.protocol("WM_DELETE_WINDOW", self.stop)
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"Error in main loop: {e}")
            self.stop()