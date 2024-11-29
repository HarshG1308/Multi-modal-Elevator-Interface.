import tkinter as tk
from elevator_app import ElevatorApp

if __name__ == "__main__":
    root = tk.Tk()
    app = ElevatorApp(root)
    app.run()