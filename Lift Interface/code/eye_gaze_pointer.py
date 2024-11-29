import tkinter as tk
import tobii_research as tr

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
        self.smoothing_factor = 0.1

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

    def show(self):
        self.deiconify()

    def hide(self):
        self.withdraw()

    def close(self):
        self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)
        self.destroy()