import threading
import time
import tobii_research as tr
import numpy as np

class EyeTracking:
    def __init__(self, app):
        self.app = app
        self.eye_tracker = None
        self.available = False
        self.stop_processing = False
        self.thread = None
        self.setup()

    def setup(self):
        try:
            found_eyetrackers = tr.find_all_eyetrackers()
            if len(found_eyetrackers) == 0:
                raise Exception("No eye trackers found")
            self.eye_tracker = found_eyetrackers[0]
            print(f"Found eye tracker: {self.eye_tracker.model}")
            self.available = True
        except Exception as e:
            print(f"Warning! Eye tracker setup failed: {e}")
            self.available = False

    def start(self):
        if not self.available:
            return
        self.stop_processing = False
        self.thread = threading.Thread(target=self._tracking_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_processing = True
        if self.thread:
            self.thread.join(timeout=1)

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def _tracking_loop(self):
        dwell_time = 1.5
        threshold = 0.8

        while not self.stop_processing:
            weights = [0.0] * len(self.app.coordinates)
            start_time = time.time()

            while time.time() - start_time < dwell_time and not self.stop_processing:
                gaze_point = self.get_gaze_point()
                if gaze_point is not None:
                    x, y = gaze_point
                    self.app.root.after(0, self.app.eye_gaze_pointer.geometry, f"+{int(x)}+{int(y)}")
                    for i, (cx, cy) in enumerate(self.app.coordinates):
                        distance = np.sqrt((x - cx)**2 + (y - cy)**2)
                        if distance < 100:  # Adjust this threshold as needed
                            weights[i] += 1

            total_weight = sum(weights)
            if total_weight > 0:
                normalized_weights = [w / total_weight for w in weights]
                max_weight = max(normalized_weights)
                if max_weight > threshold:
                    selected_index = normalized_weights.index(max_weight)
                    self.app.root.after(0, self.app.select_item, selected_index)

    def get_gaze_data(self):
        gaze_data = {}
        def gaze_data_callback(gaze_data_):
            nonlocal gaze_data
            gaze_data = gaze_data_

        self.eye_tracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
        time.sleep(0.1)  # Wait a short time to collect gaze data
        self.eye_tracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)

        if gaze_data:
            left_eye = gaze_data.get('left_gaze_point_on_display_area', (0, 0))
            right_eye = gaze_data.get('right_gaze_point_on_display_area', (0, 0))
            x = (left_eye[0] + right_eye[0]) / 2
            y = (left_eye[1] + right_eye[1]) / 2
            return x * self.app.winfo_screenwidth(), y * self.app.winfo_screenheight()
        return None
    
            