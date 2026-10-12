# This module manages multiple IP Webcam streams (one per lane) in parallel.
# It also provides a simulation fallback when a camera URL is unreachable.
# It uses OpenCV to grab frames and Python threads to run each lane continuously.
# Every line in this file includes beginner-friendly comments, as requested.

# Import threading so we can run each camera lane in its own thread.
import threading  # Threading for parallel camera reads.

# Import time so we can handle delays, timestamps, and reconnect intervals.
import time  # Time utilities for countdowns and reconnect logic.

# Import random so the simulation can generate varied fake vehicle data.
import random  # Random values for simulation mode.

# Import typing for type hints (helps beginners understand data shapes).
from typing import Dict, Optional, Any  # Type hints for readability.

# Import OpenCV so we can open and read frames from IP webcam streams.
import cv2  # OpenCV handles camera streams and image drawing.

# Import numpy so we can create fake frames in simulation mode.
import numpy as np  # Numpy arrays store images (frames) in memory.


# Create the CameraManager class as the main entry point for camera control.
class CameraManager:  # This class owns threads and latest frames per lane.
    # The constructor receives lane->URL mapping and starts internal settings.
    def __init__(  # __init__ sets up state but does not start threads automatically.
        self,  # self refers to the current CameraManager instance.
        cameras: Dict[str, str],  # cameras maps lane names (keys) to IP URLs (values).
        reconnect_interval_seconds: int = 10,  # reconnect_interval_seconds controls reconnection attempts.
        simulation_fps: int = 10,  # simulation_fps controls how fast fake frames update.
        frame_size: tuple = (480, 640),  # frame_size is (height, width) for simulated frames.
    ):  # End of constructor signature.
        # Store the cameras mapping for later use in thread workers.
        self.cameras: Dict[str, str] = cameras  # Keep the lane->URL dictionary.

        # Store reconnect interval so each lane knows when to retry connecting.
        self.reconnect_interval_seconds: int = reconnect_interval_seconds  # Save reconnection interval.

        # Store how many frames per second to simulate when streams are down.
        self.simulation_fps: int = simulation_fps  # Save simulation FPS.

        # Store frame size for simulation images.
        self.frame_size: tuple = frame_size  # Save frame size (height, width).

        # Create a lock so multiple threads can safely update shared frame buffers.
        self._lock: threading.Lock = threading.Lock()  # Prevent race conditions on shared dicts.

        # Store latest frames in a dictionary keyed by lane name.
        self._latest_frames: Dict[str, np.ndarray] = {}  # Latest camera frame per lane.

        # Store whether each lane is currently in simulation fallback.
        self._lane_simulation_mode: Dict[str, bool] = {}  # Track simulation status per lane.

        # Store timestamps of last successful frame updates per lane.
        self._lane_last_frame_time: Dict[str, float] = {}  # Track time of last frame for monitoring.

        # Store the worker threads so we can join/stop later.
        self._threads: Dict[str, threading.Thread] = {}  # Thread objects per lane.

        # Use an event object to signal threads to stop gracefully.
        self._stop_event: threading.Event = threading.Event()  # Stop flag for all worker loops.

        # Initialize per-lane simulation mode and last-frame times.
        for lane_name in self.cameras.keys():  # Loop over each lane key in the mapping.
            self._lane_simulation_mode[lane_name] = False  # Start assuming real camera is available.
            self._lane_last_frame_time[lane_name] = 0.0  # No frames yet when manager starts.

    # Start all camera threads so each lane begins reading frames immediately.
    def start(self) -> None:  # start() will create and launch one thread per lane.
        # Clear the stop event in case this object is reused.
        self._stop_event.clear()  # Ensure stop flag is not set.

        # Create one thread per lane and start them.
        for lane_name, url in self.cameras.items():  # Iterate each lane and its URL.
            # Create a thread object targeting the private worker method.
            t: threading.Thread = threading.Thread(  # Create worker thread.
                target=self._lane_worker,  # The function each thread will run.
                args=(lane_name, url),  # Pass lane_name and url to the worker.
                daemon=True,  # daemon=True so threads do not block program exit.
            )  # End thread creation.

            # Store the thread for possible later stopping/joining.
            self._threads[lane_name] = t  # Save thread reference.

            # Start the thread now so it begins reading frames.
            t.start()  # Launch the worker loop.

    # Stop all camera threads by setting the stop event.
    def stop(self) -> None:  # stop() signals workers to exit their loops.
        # Signal threads to stop.
        self._stop_event.set()  # Set stop flag.

        # Join each thread briefly to let them end cleanly.
        for lane_name, t in self._threads.items():  # Loop through all lane threads.
            # Join waits for thread completion.
            t.join(timeout=2.0)  # Give a small timeout to prevent hanging forever.

    # Private helper: create a simulated frame for a lane.
    def _generate_simulated_frame(self, lane_name: str, tick: int) -> np.ndarray:  # Create one fake frame as numpy array.
        # Unpack frame size into height and width.
        height, width = self.frame_size  # height rows and width columns.

        # Create a blank dark frame as base background.
        frame: np.ndarray = np.zeros((height, width, 3), dtype=np.uint8)  # Black image.

        # Fill background slightly darker to avoid pure black look.
        frame[:] = (10, 10, 20)  # Base color for a professional dark UI feel.

        # Choose a lane color to visually distinguish lanes.
        lane_color = (  # lane_color is a BGR tuple used by OpenCV drawing.
            0 + (hash(lane_name) % 120),  # Blue channel varies per lane.
            180 + (hash(lane_name) % 70),  # Green channel varies per lane.
            100 + (hash(lane_name) % 80),  # Red channel varies per lane.
        )  # End lane_color selection.

        # Draw a lane rectangle representing road area.
        cv2.rectangle(frame, (20, 20), (width - 20, height - 20), lane_color, 2)  # Road boundary.

        # Draw lane name label at the top-left.
        cv2.putText(  # OpenCV text drawing.
            frame,  # Image to draw on.
            f"SIMULATED: {lane_name}",  # Text content.
            (30, 60),  # Text position.
            cv2.FONT_HERSHEY_SIMPLEX,  # Font style.
            0.8,  # Font scale.
            (255, 255, 255),  # Text color (white).
            2,  # Thickness.
            cv2.LINE_AA,  # Anti-aliasing for smoother text.
        )  # Done drawing lane label.

        # Create some fake vehicle rectangles that move with `tick`.
        for i in range(3):  # Draw three fake vehicles per frame for realism.
            # Generate a consistent pseudo-random lane offset per vehicle.
            base_x = 60 + i * 120  # Spread vehicles across the road width.

            # Move vehicles left/right over time using tick.
            x = int(base_x + (tick * 5) % 80)  # Horizontal motion pattern.

            # Choose a y position that depends on i so they don't overlap exactly.
            y = 120 + i * 60  # Vertical placement.

            # Make a rectangle size that looks like a vehicle.
            rect_w = 70  # Vehicle width.
            rect_h = 30  # Vehicle height.

            # Compute top-left and bottom-right corners.
            tl = (x, y)  # Top-left corner.
            br = (x + rect_w, y + rect_h)  # Bottom-right corner.

            # Alternate vehicle colors for variety.
            vehicle_color = (  # BGR color for each simulated vehicle.
                random.randint(0, 255),  # Blue component.
                random.randint(0, 255),  # Green component.
                random.randint(0, 255),  # Red component.
            )  # End vehicle color.

            # Draw the vehicle rectangle.
            cv2.rectangle(frame, tl, br, vehicle_color, -1)  # Filled rectangle.

            # Draw a lighter border on top for a nicer look.
            cv2.rectangle(frame, tl, br, (255, 255, 255), 1)  # Border line.

        # Add a small status text showing tick value.
        cv2.putText(  # Draw another label with tick counter.
            frame,  # Frame image to draw on.
            f"Tick: {tick}",  # Tick value label.
            (30, height - 30),  # Bottom-left position.
            cv2.FONT_HERSHEY_SIMPLEX,  # Same font.
            0.7,  # Font scale.
            (200, 220, 255),  # Soft text color.
            2,  # Thickness.
            cv2.LINE_AA,  # Smooth text.
        )  # End tick label.

        # Return the simulated frame for this lane.
        return frame  # Provide numpy image array.

    # Private helper: the worker loop for a single lane.
    def _lane_worker(self, lane_name: str, url: str) -> None:  # Worker runs forever until stop event is set.
        # Create variables to track OpenCV capture object and reconnection time.
        cap: Optional[cv2.VideoCapture] = None  # cap will store VideoCapture when available.
        simulation_mode: bool = False  # True means we generate fake frames instead of reading camera.
        tick: int = 0  # tick is a frame counter used for simulation animation.
        last_reconnect_attempt: float = 0.0  # track time of last reconnect attempt.

        # Main loop: runs until stop event is set.
        while not self._stop_event.is_set():  # Check stop flag each iteration.
            # Get current time in seconds.
            now: float = time.time()  # Timestamp for decisions.

            # If we have no capture or it is not opened, try to connect/reconnect.
            if cap is None or not cap.isOpened():  # Detect connection loss.
                # Mark lane as simulation until connection is successful.
                simulation_mode = True  # Turn on simulation immediately.

                # If cap object exists, release it to free resources.
                if cap is not None:  # Only release if cap was created.
                    cap.release()  # Close underlying stream.
                    cap = None  # Reset cap reference.

                # Check if enough time passed since last reconnect attempt.
                if (now - last_reconnect_attempt) >= self.reconnect_interval_seconds:  # Reconnect interval rule.
                    # Update last reconnect attempt time.
                    last_reconnect_attempt = now  # Save new attempt time.

                    # Try to open the camera stream again.
                    cap = cv2.VideoCapture(url)  # Create VideoCapture for this URL.

                    # Optionally reduce buffering to get newer frames quickly.
                    # Note: CAP_PROP_BUFFERSIZE may not work for all camera drivers.
                    try:  # Use try because some OpenCV builds may not support this property.
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Ask OpenCV to keep buffer small.
                    except Exception:  # If property fails, ignore and continue.
                        pass  # Keep going without changing buffers.

                    # If capture opened successfully, exit simulation mode.
                    if cap is not None and cap.isOpened():  # Connection succeeded.
                        simulation_mode = False  # Switch back to real camera frames.

            # If we are in simulation mode, generate frames and keep running.
            if simulation_mode:  # Simulation mode means we cannot read real frames.
                # Generate a simulated frame for this lane.
                frame_sim: np.ndarray = self._generate_simulated_frame(lane_name, tick)  # Fake traffic frame.

                # Lock while updating shared latest frame storage.
                with self._lock:  # Ensure thread-safe dictionary update.
                    self._latest_frames[lane_name] = frame_sim  # Save simulated frame as latest.
                    self._lane_simulation_mode[lane_name] = True  # Mark lane in simulation.
                    self._lane_last_frame_time[lane_name] = now  # Update last frame time.

                # Increment tick counter for animation movement.
                tick += 1  # Move simulation forward in time.

                # Sleep to control simulation FPS and reduce CPU usage.
                time.sleep(1.0 / float(self.simulation_fps))  # Wait a bit before generating next frame.
                # Continue to next loop iteration.
                continue  # Skip real capture logic.

            # If not simulation, try reading a real frame from OpenCV.
            assert cap is not None  # Help the reader: cap should exist when simulation_mode is False.
            ok: bool
            frame: np.ndarray
            ok, frame = cap.read()  # Read one frame from the camera stream.

            # If reading succeeded, store this frame as the latest frame.
            if ok and frame is not None:  # Ensure frame is valid.
                # Lock while updating shared latest frame storage.
                with self._lock:  # Prevent data corruption across threads.
                    self._latest_frames[lane_name] = frame  # Save latest real camera frame.
                    self._lane_simulation_mode[lane_name] = False  # Mark lane in real mode.
                    self._lane_last_frame_time[lane_name] = now  # Update last frame time.

                # Increment tick counter (optional for monitoring).
                tick += 1  # Tick may help simulation if fallback happens.

                # Small sleep reduces CPU usage when cameras are very fast.
                time.sleep(0.01)  # Avoid busy-waiting.
            else:  # If reading failed, switch to simulation and reconnect later.
                # Mark simulation mode; the top of loop will try reconnect every interval.
                simulation_mode = True  # Switch off real frames.

                # Release capture so reconnect attempt will recreate it.
                if cap is not None:  # Only if cap exists.
                    cap.release()  # Release the broken stream.
                    cap = None  # Reset for reconnect cycle.

                # Add a short sleep so we do not hammer CPU too fast.
                time.sleep(0.05)  # Small delay before the next loop iteration.

    # Get the latest frame for a single lane name.
    def get_frame(self, lane_name: str) -> Optional[np.ndarray]:  # Return numpy frame or None.
        # Lock while reading shared state for safety.
        with self._lock:  # Prevent inconsistent reads during updates.
            # Return the stored latest frame (or None if lane not found yet).
            return self._latest_frames.get(lane_name)  # Latest frame for lane.

    # Get the latest frames for all lanes as a dictionary.
    def get_all_frames(self) -> Dict[str, np.ndarray]:  # Return lane->frame for lanes with frames.
        # Lock while copying shared latest frames to avoid race conditions.
        with self._lock:  # Protect shared dict.
            # Create a shallow copy so caller cannot break internal state.
            return dict(self._latest_frames)  # Return copy of latest frames.

    # Helper to expose whether a lane is in simulation mode.
    def is_lane_simulating(self, lane_name: str) -> bool:  # Return True if simulation is active.
        # Lock while reading the simulation mode dict.
        with self._lock:  # Ensure thread-safe access.
            # Return simulation status for the lane (default False).
            return bool(self._lane_simulation_mode.get(lane_name, False))  # Simulation status.


# We keep one global manager instance to support module-level functions.
_global_manager: Optional[CameraManager] = None  # This variable stores the active manager.


# Initialize the camera manager using a lane->URL dictionary.
def start_camera_manager(  # This is a helper to create and start the global manager.
    cameras: Dict[str, str],  # cameras maps lane names to IP Webcam URLs.
    reconnect_interval_seconds: int = 10,  # Reconnect interval for broken streams.
    simulation_fps: int = 10,  # FPS for simulation fallback frames.
    frame_size: tuple = (480, 640),  # Size for generated simulated frames.
) -> CameraManager:  # Return the created manager instance.
    # Create the CameraManager with passed settings.
    global _global_manager  # We will assign to the module-level variable.
    _global_manager = CameraManager(  # Construct a new manager object.
        cameras=cameras,  # Pass the lane->URL mapping.
        reconnect_interval_seconds=reconnect_interval_seconds,  # Set reconnect interval.
        simulation_fps=simulation_fps,  # Set simulation FPS.
        frame_size=frame_size,  # Set simulation frame size.
    )  # End CameraManager construction.

    # Start all lane threads so cameras/simulation begin immediately.
    _global_manager.start()  # Launch worker threads.

    # Return the started manager.
    return _global_manager  # Provide reference to callers.


# Module-level function: get the latest frame for a lane.
def get_frame(lane_name: str) -> Optional[np.ndarray]:  # Return numpy frame or None.
    # If no manager is running, we return None.
    if _global_manager is None:  # Check global manager state.
        return None  # Caller can handle this case.

    # Delegate to the global manager instance.
    return _global_manager.get_frame(lane_name)  # Fetch latest frame.


# Module-level function: get latest frames for all lanes.
def get_all_frames() -> Dict[str, np.ndarray]:  # Return dictionary lane->frame.
    # If no manager exists yet, return empty dict.
    if _global_manager is None:  # No started manager.
        return {}  # Return empty frames dict.

    # Delegate to the global manager instance.
    return _global_manager.get_all_frames()  # Return latest frames for all lanes.

