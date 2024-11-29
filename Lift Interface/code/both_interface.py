import json
import threading
import time
import tkinter as tk
from tkinter import messagebox

import numpy as np
import pyaudio
import pyttsx3
# from pytribe import EyeTribe
from vosk import KaldiRecognizer, Model

# coordinates = [None] * 9

# def get_box_centers():
#     global coordinates

#     for i, button in enumerate(floor_buttons):
#         button.update_idletasks()
#         x = button.winfo_x() + button.winfo_width() + 165
#         y = button.winfo_y() + button.winfo_height() + 130
#         coordinates[i] = [x, y]
#     # Place the points on the buttons
#     for i, (x, y) in enumerate(coordinates):
#         point = tk.Label(root, text="O", font=("Arial", 10), bg="red", foreground="white")
#         point.place(x=x, y=y, anchor="center")



# try:    
#     eye_tracker = EyeTribe()
# except:
#     print("Warning! eye tracker device is not connected.")

# def get_nearest_box():
#     global eye_tracker
#     try:
#         eye_tracker.start_recording()
#     except:
#         messagebox.showerror("Eye tracker error", "Eye tracker device is not connected.")
#         return (None, None, None, None, None)
    
#     frame = eye_tracker._tracker.get_frame()
#     x, y = frame['avgx'], frame['avgy']

#     if x == 0 and y == 0:
#         return (None, None, None, None, None)

#     eye_tracker.stop_recording()

#     distances = []
#     for i in range(9):
#         distance = np.sqrt((x - coordinates[i][0])**2 + (y - coordinates[i][1])**2)
#         distances.append(distance)
    
#     box = np.argmin(distances)
    
#     return (int(box), x, y, frame['Lpsize'], frame['Rpsize'])
    

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)  # Set speaking speed

def speak(text):
    engine.say(text)
    engine.runAndWait()

# Initialize Vosk model and recognizer with custom grammar
model_path = r"Lift Interface\vosk-model-en-in-0.5"

# Load the custom grammar
grammar = {
    "type": "list",
    "items": [
        "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "ten",
        "open door", "close door", "emergency",
        "first", "second", "third", "fourth", "fifth",
        "sixth", "seventh", "eighth", "ninth", "tenth"
    ]
}

# increase weight of the grammar in the recognizer
model = Model(model_path)

recognizer = KaldiRecognizer(model, 16000, json.dumps(grammar))

# Map spelled-out numbers to their corresponding integers
number_map = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
    "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10
}

def recognize_speech_from_mic():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4096)
    stream.start_stream()
    listening_label.pack()
    root.update()
    print("Listening...")
        
    while True:
        data = stream.read(4096, exception_on_overflow=False)
        if recognizer.AcceptWaveform(data):
            result = recognizer.Result()
            text = json.loads(result).get("text", "")
            if text:
                listening_label.pack_forget()
                return text

def move_elevator(target_floor):
    if door_status_var.get() == "Open":
        floor_label.config(text="Please close the door first")
        speak("Please close the door first")
        return
    current_floor = current_floor_var.get()
    if current_floor == target_floor:
        speak(f"Already at Floor {target_floor}")
        floor_buttons[target_floor - 1].config(bg="white", state=tk.NORMAL)
        return
    direction = 1 if target_floor > current_floor else -1
    floors = range(current_floor, target_floor + direction, direction)
    for floor in floors:
        current_floor_var.set(floor)
        floor_label.config(text=f"Floor: {floor}")
        slider.set(floor)
        update_arrow_direction(current_floor, target_floor)

        # Update outer interface
        outer_floor_label.config(text=f"Floor: {floor}")
        update_outer_direction(current_floor, target_floor, outer_direction_label)
        update_elevator_position(floor, canvas_height, outer_canvas, elevator_rect)

        root.update()
        outer_root.update()
        time.sleep(0.8)
    close_door()
    speak(f"Arrived at Floor {target_floor}")
    floor_buttons[target_floor - 1].config(bg="#3498db", state=tk.NORMAL)  # Reset button color


def update_arrow_direction(current_floor, target_floor):
    if current_floor < target_floor:
        arrow_label.config(text="↑")
    elif current_floor > target_floor:
        arrow_label.config(text="↓")
    else:
        arrow_label.config(text="")
    root.update()

def update_outer_direction(current_floor, target_floor, label):
    if current_floor < target_floor:
        label.config(text="↑")
    elif current_floor > target_floor:
        label.config(text="↓")
    else:
        label.config(text="")

def update_elevator_position(floor, canvas_height, canvas, rect):
    max_floors = 9
    floor_height = canvas_height / max_floors
    y = canvas_height - (floor * floor_height)
    canvas.coords(rect, 10, y, canvas.winfo_width() - 10, y + 50)

def open_door():
    door_status_var.set("Open")
    door_status_label.config(text="Door: Opened")

def close_door():
    door_status_var.set("Closed")
    door_status_label.config(text="Door: Closed")

def handle_floor_button(target_floor):
    if door_status_var.get() == "Open":
        floor_label.config(text="Please close the door first")
        speak("Please close the door first")
    else:
        floor_buttons[target_floor - 1].config(state=tk.DISABLED, bg="yellow")
        move_elevator(target_floor)

def handle_voice_command():
    command = recognize_speech_from_mic()
    print(f"You said: {command}")
    target_floor = 0
    try:
        for word, number in number_map.items():
            if word in command:
                target_floor = number
                break
        if target_floor > max_floors or target_floor < 1:
            floor_label.config(text="Invalid floor number")
            speak("Invalid floor number")
        elif target_floor == 0:
            speak("Unable to recognize")
        else:
            handle_floor_button(target_floor)
        if "open" in command:
            open_door()
        elif "close" in command:
            close_door()
        elif "emergency" in command:
            simulate_emergency()
    except Exception as e:
        print(e)
        speak("Unable to recognize")

def simulate_emergency():
    speak("Emergency button pressed. Elevator stopped.")
    root.destroy()
    outer_root.destroy()

# Root window setup
root = tk.Tk()
root.title("Voice-Activated Elevator Interface")
root.geometry("1000x600")
root.configure(bg="#3498db")  # Blue background

# maximum number of floors
max_floors = 9

# Header
heading_label = tk.Label(root, text="Voice-Activated Elevator Interface", font=("Arial", 24, "bold"), bg="#3498db", fg="white")
heading_label.pack(pady=10)

# Main panel frame
panel_frame = tk.Frame(root, bg="#3498db")
panel_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

# Floor panel
floor_panel = tk.Frame(panel_frame, bg="#ecf0f1", padx=20, pady=20, bd=2, relief=tk.SUNKEN)
floor_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

floor_panel_label = tk.Label(floor_panel, text="Floor Panel", font=("Arial", 16, "bold"), bg="#ecf0f1", fg="#3498db")
floor_panel_label.pack(pady=10)

# Floor buttons
floor_button_frame = tk.Frame(floor_panel, bg="#ecf0f1")
floor_button_frame.pack(pady=10)

floor_buttons = []
for floor in range(1, max_floors + 1):
    button = tk.Button(floor_button_frame, text=f"Floor {floor}", command=lambda f=floor: handle_floor_button(f),
                       font=("Arial", 12), bg="#3498db", fg="white", padx=20, pady=20, activebackground="#2980b9", activeforeground="white")
    button.grid(row=(floor - 1) // 3, column=(floor - 1) % 3, padx=5, pady=5)
    floor_buttons.append(button)

# Additional buttons
additional_button_frame = tk.Frame(floor_panel, bg="#ecf0f1")
additional_button_frame.pack(pady=10)

open_button = tk.Button(additional_button_frame, text="Open Door", command=open_door, font=("Arial", 12), bg="#2ecc71", fg="white", padx=20, pady=20, activebackground="#27ae60", activeforeground="white")
open_button.grid(row=0, column=0, padx=5, pady=5)

close_button = tk.Button(additional_button_frame, text="Close Door", command=close_door, font=("Arial", 12), bg="#e74c3c", fg="white", padx=20, pady=20, activebackground="#c0392b", activeforeground="white")
close_button.grid(row=0, column=1, padx=5, pady=5)

emergency_button = tk.Button(additional_button_frame, text="Emergency", command=simulate_emergency, font=("Arial", 12), bg="#f39c12", fg="white", padx=20, pady=20, activebackground="#e67e22", activeforeground="white")
emergency_button.grid(row=0, column=2, padx=5, pady=5)

# Elevator panel
elevator_panel = tk.Frame(panel_frame, bg="#ecf0f1", padx=20, pady=20, bd=2, relief=tk.SUNKEN)
elevator_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

current_floor_label = tk.Label(elevator_panel, text="Current Floor: ", font=("Arial", 16), bg="#ecf0f1", fg="#3498db")
current_floor_label.pack(pady=10, side=tk.LEFT, padx=20)

current_floor_var = tk.IntVar(value=1)  # Default current floor is 1
floor_label = tk.Label(elevator_panel, textvariable=current_floor_var, font=("Arial", 24), bg="#ecf0f1")
floor_label.pack(pady=10, side=tk.LEFT, padx=20)

arrow_label = tk.Label(elevator_panel, text="", font=("Arial", 24), bg="#ecf0f1")
arrow_label.pack(pady=10, side=tk.LEFT, padx=20)

slider = tk.Scale(elevator_panel, from_=max_floors, to=1, orient=tk.VERTICAL, length=450, width= 60, tickinterval=1, font=("Arial", 12), bg="#ecf0f1", fg="#333333", highlightthickness=0)
slider.set(current_floor_var.get())
slider.pack(pady=20)

# Door status label
door_label = tk.Label(elevator_panel, text="Door: ", font=("Arial", 16), bg="#ecf0f1", fg="#3498db")
door_label.pack(pady=10, side=tk.LEFT, padx=10)

door_status_var = tk.StringVar(value="Closed")
door_status_label = tk.Label(elevator_panel, textvariable=door_status_var, font=("Arial", 16), bg="#ecf0f1")
door_status_label.pack(pady=10, side=tk.LEFT, padx=10)


# Listening label
listening_label = tk.Label(root, text="Listening...", font=("Arial", 16), bg="#3498db", fg="white")

# Outer interface setup
outer_root = tk.Toplevel(root)
outer_root.title("Elevator Outer Interface")
outer_root.geometry("500x700")
outer_root.configure(bg="#3498db")  # Dark blue background

# Header
header_frame = tk.Frame(outer_root, bg="#3498db")
header_frame.pack(pady=10)

header_label = tk.Label(header_frame, text="Elevator Outer Interface", font=("Arial", 20, "bold"), fg="white", bg="#3498db")
header_label.pack()

# Floor display
floor_display_frame = tk.Frame(outer_root, bg="#3498db")
floor_display_frame.pack(pady=10)

outer_floor_label = tk.Label(floor_display_frame, text="Floor: 1", font=("Arial", 24), bg="#3498db", fg="white")
outer_floor_label.pack(side=tk.LEFT, padx=10)

outer_direction_label = tk.Label(floor_display_frame, text="", font=("Arial", 24), bg="#3498db", fg="white")
outer_direction_label.pack(side=tk.LEFT, padx=10)

# Canvas and elevator position
canvas_frame = tk.Frame(outer_root, bg="#3498db")
canvas_frame.pack(pady=10)

canvas_width = 300
canvas_height = 500

outer_canvas = tk.Canvas(canvas_frame, width=canvas_width, height=canvas_height, bg="#ecf0f1", highlightthickness=0) 
outer_canvas.pack(side=tk.LEFT, padx=10, pady=10)

# Elevator rectangle
elevator_rect = outer_canvas.create_rectangle(10, 10, canvas_width - 10, 60, fill="powder blue", outline="") 

# Floor numbers
floor_numbers_frame = tk.Frame(canvas_frame, bg="#3498db")
floor_numbers_frame.pack(side=tk.RIGHT, padx=10, fill=tk.Y)

floor_height = canvas_height / max_floors
for floor in range(max_floors, 0, -1):
    y = canvas_height - (floor * floor_height)
    floor_label = tk.Label(floor_numbers_frame, text=f"{floor}", font=("Arial", 16), fg="black", padx=10, pady=8)
    floor_label.pack(pady=6)

# Footer
footer_frame = tk.Frame(outer_root, bg="#3498db")
footer_frame.pack(pady=10, fill=tk.X)

footer_label = tk.Label(footer_frame, text="© 2023 Elevator Co.", font=("Arial", 12), fg="white", bg="#3498db")
footer_label.pack()

# Start the speech recognition thread
def start_voice_recognition():
    while True:
        handle_voice_command()

voice_thread = threading.Thread(target=start_voice_recognition)
voice_thread.daemon = True
voice_thread.start()

# get_box_centers()

root.mainloop()