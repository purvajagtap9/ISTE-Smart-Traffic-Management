# This module estimates vehicle speed using Lucas-Kanade Optical Flow.
# It is meant for a stationary camera per lane (fixed camera viewpoint).
# The module is designed for beginner use and adds comments on every line.

# We import random so we can generate simulated speeds when optical flow fails.
import random  # Random is used for demo fallback speeds.

# We import typing helpers so function signatures are clear.
from typing import Optional, Tuple  # Optional allows None values; Tuple helps with bbox types.

# We import cv2 to use OpenCV optical flow and drawing tools.
import cv2  # OpenCV provides calcOpticalFlowPyrLK and putText/rectangle.

# We import numpy because frames are numpy arrays in OpenCV.
import numpy as np  # Numpy is used for numeric operations.


# We define the default optical flow calibration:
# "100 pixels = 5 meters" => pixels_per_meter = 100 / 5 = 20 px per meter.
DEFAULT_PIXELS_PER_METER: float = 20.0  # Default calibration factor for conversion to meters.

# We define the default demo speed limit as requested.
DEFAULT_SPEED_LIMIT_KMH: float = 40.0  # Speed limit for flagging speeding violations.

# We define a default FPS to convert "per-frame displacement" into "per-second speed".
# If your camera runs at a different FPS, pass fps=... to estimate_speed().
DEFAULT_FPS: float = 10.0  # Default frame rate used for speed calculation in this demo.


def _simulate_speed_and_flag(  # Helper to generate fallback speed values.
    speed_limit_kmh: float,  # Speed limit for deciding violation.
) -> Tuple[float, bool]:  # Returns (speed_kmh, is_violation).
    # Generate a random speed between 20 and 80 km/h as requested.
    simulated_speed_kmh: float = random.uniform(20.0, 80.0)  # Random demo speed value.
    # Decide if this is a violation based on the speed limit.
    is_violation: bool = simulated_speed_kmh > speed_limit_kmh  # True if exceeding the limit.
    # Return both values to the caller.
    return simulated_speed_kmh, is_violation  # Output values for downstream logic.


def _clamp_bbox_to_frame(  # Helper to ensure bbox coordinates are valid within the frame.
    bbox: Tuple[int, int, int, int],  # Input bbox as (x1, y1, x2, y2).
    frame_w: int,  # Frame width in pixels.
    frame_h: int,  # Frame height in pixels.
) -> Tuple[int, int, int, int]:  # Returns a clamped bbox.
    # Unpack bbox coordinates for readability.
    x1, y1, x2, y2 = bbox  # Extract coordinates.
    # Clamp x1 between 0 and frame width - 1.
    x1 = max(0, min(x1, frame_w - 1))  # Keep x1 in bounds.
    # Clamp y1 between 0 and frame height - 1.
    y1 = max(0, min(y1, frame_h - 1))  # Keep y1 in bounds.
    # Clamp x2 between 0 and frame width - 1.
    x2 = max(0, min(x2, frame_w - 1))  # Keep x2 in bounds.
    # Clamp y2 between 0 and frame height - 1.
    y2 = max(0, min(y2, frame_h - 1))  # Keep y2 in bounds.
    # Ensure x2 is after x1 by enforcing minimum width of 1 pixel.
    if x2 <= x1:  # If bbox is too thin or reversed,
        x2 = min(frame_w - 1, x1 + 1)  # Expand bbox to at least 1 pixel.
    # Ensure y2 is after y1 by enforcing minimum height of 1 pixel.
    if y2 <= y1:  # If bbox height is too small or reversed,
        y2 = min(frame_h - 1, y1 + 1)  # Expand bbox to at least 1 pixel.
    # Return the corrected bbox values.
    return x1, y1, x2, y2  # Output clamped bbox.


def estimate_speed(  # Main function that estimates speed from two consecutive frames.
    prev_frame: np.ndarray,  # Previous frame (t-1).
    curr_frame: np.ndarray,  # Current frame (t).
    vehicle_bbox: Optional[Tuple[int, int, int, int]] = None,  # Optional bbox to limit optical flow to the vehicle.
    *,  # Force the remaining arguments to be keyword-only for safer usage.
    pixels_per_meter: float = DEFAULT_PIXELS_PER_METER,  # Calibration: pixels -> meters conversion factor.
    fps: float = DEFAULT_FPS,  # Frames per second for speed conversion.
    speed_limit_kmh: float = DEFAULT_SPEED_LIMIT_KMH,  # Speed limit for violation flagging.
    max_features: int = 200,  # Maximum corners/features to track (more = potentially more accurate but slower).
    min_track_points: int = 8,  # Minimum number of successfully tracked points required for a valid estimate.
) -> Tuple[float, bool, np.ndarray]:  # Returns (speed_kmh, is_violation, annotated_frame).
    # First, copy the current frame because we will draw annotations on it.
    annotated: np.ndarray = curr_frame.copy()  # Keep original frame unmodified.

    # If frames are missing, we cannot run optical flow, so we simulate a speed.
    if prev_frame is None or curr_frame is None:  # Defensive check for robustness.
        speed_kmh, is_violation = _simulate_speed_and_flag(speed_limit_kmh=speed_limit_kmh)  # Fallback to simulation.
        # Choose color based on violation.
        color = (0, 0, 255) if is_violation else (0, 255, 0)  # Red for violation, green otherwise.
        # Put speed text near the top-left corner of the frame.
        cv2.putText(annotated, f"{speed_kmh:.1f} km/h", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)  # Draw speed.
        # Return the simulated result.
        return speed_kmh, is_violation, annotated  # Output speed estimation with annotation.

    # Get frame height and width for ROI calculations.
    frame_h: int = curr_frame.shape[0]  # Height dimension for cv2 arrays.
    frame_w: int = curr_frame.shape[1]  # Width dimension for cv2 arrays.

    # Convert previous frame to grayscale because optical flow works on intensity images.
    prev_gray: np.ndarray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)  # Grayscale conversion.
    # Convert current frame to grayscale.
    curr_gray: np.ndarray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)  # Grayscale conversion.

    # Decide the region-of-interest (ROI) where we will track motion.
    # If vehicle_bbox is provided, we track inside that box.
    # Otherwise, we track on the whole frame (less accurate, but works as a default).
    if vehicle_bbox is not None:  # If user gave us a vehicle bounding box,
        # Clamp bbox to frame boundaries so slicing never goes out of range.
        x1, y1, x2, y2 = _clamp_bbox_to_frame(  # Correct bbox coordinates.
            bbox=vehicle_bbox,  # Pass input bbox.
            frame_w=frame_w,  # Provide frame width for clamping.
            frame_h=frame_h,  # Provide frame height for clamping.
        )  # End clamping.
        # Crop grayscale images to the vehicle ROI.
        prev_roi: np.ndarray = prev_gray[y1:y2, x1:x2]  # Previous ROI for tracking.
        curr_roi: np.ndarray = curr_gray[y1:y2, x1:x2]  # Current ROI for tracking.
        # We'll draw text near the top-left corner of the bbox in the original image.
        text_origin_x: int = x1  # X coordinate for annotation text.
        text_origin_y: int = max(0, y1 - 10)  # Y coordinate with a small offset above bbox.
    else:  # If no bbox is given,
        # Use the entire frame as ROI.
        prev_roi = prev_gray  # Use whole previous grayscale frame.
        curr_roi = curr_gray  # Use whole current grayscale frame.
        # Draw speed at a convenient place (top-left).
        text_origin_x = 10  # Annotation X coordinate.
        text_origin_y = 30  # Annotation Y coordinate.

    # Detect good features to track (corners) in the previous ROI.
    # These points are what we will track to measure displacement.
    prev_points: Optional[np.ndarray] = cv2.goodFeaturesToTrack(  # Find strong corners.
        prev_roi,  # ROI image to find corners in.
        maxCorners=max_features,  # Maximum number of corners.
        qualityLevel=0.01,  # Minimum quality of corners (lower = more points).
        minDistance=7,  # Minimum distance between corners.
        blockSize=7,  # Size of the block used for computing an average derivative.
    )  # End goodFeaturesToTrack call.

    # If we couldn't find points, we consider optical flow unreliable and simulate speed.
    if prev_points is None or len(prev_points) == 0:  # If no tracking points were found,
        speed_kmh, is_violation = _simulate_speed_and_flag(speed_limit_kmh=speed_limit_kmh)  # Simulate fallback speed.
        # Choose annotation color based on violation.
        color = (0, 0, 255) if is_violation else (0, 255, 0)  # Red if speeding, green otherwise.
        # Draw the speed text on the annotated frame.
        cv2.putText(annotated, f"{speed_kmh:.1f} km/h", (text_origin_x, text_origin_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)  # Draw text.
        # Return simulated output.
        return speed_kmh, is_violation, annotated  # Output.

    # Track the detected points from prev_roi to curr_roi using Lucas-Kanade Optical Flow.
    next_points, status, _error = cv2.calcOpticalFlowPyrLK(  # Track points between frames.
        prev_roi,  # Previous ROI grayscale.
        curr_roi,  # Current ROI grayscale.
        prev_points,  # Points detected in previous ROI.
        None,  # We do not provide initial guess for next points.
        winSize=(15, 15),  # Window size for searching corresponding points.
        maxLevel=2,  # Pyramid levels (multi-scale tracking).
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),  # Stop criteria for iteration.
    )  # End calcOpticalFlowPyrLK call.

    # If optical flow failed to return points, simulate speed.
    if next_points is None or status is None:  # Safety check.
        speed_kmh, is_violation = _simulate_speed_and_flag(speed_limit_kmh=speed_limit_kmh)  # Simulated fallback.
        color = (0, 0, 255) if is_violation else (0, 255, 0)  # Red/green annotation color.
        cv2.putText(annotated, f"{speed_kmh:.1f} km/h", (text_origin_x, text_origin_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)  # Draw.
        return speed_kmh, is_violation, annotated  # Return fallback.

    # Convert status array to a boolean mask for successfully tracked points.
    status_mask: np.ndarray = status.flatten() == 1  # True for good tracks.

    # Extract only the successfully tracked points.
    good_prev: np.ndarray = prev_points[status_mask]  # Previous good points.
    good_next: np.ndarray = next_points[status_mask]  # Current good points.

    # If too few points were tracked successfully, treat optical flow as failed.
    if good_prev.shape[0] < min_track_points:  # If insufficient tracking quality,
        speed_kmh, is_violation = _simulate_speed_and_flag(speed_limit_kmh=speed_limit_kmh)  # Simulate fallback speed.
        color = (0, 0, 255) if is_violation else (0, 255, 0)  # Pick annotation color.
        cv2.putText(annotated, f"{speed_kmh:.1f} km/h", (text_origin_x, text_origin_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)  # Draw speed text.
        return speed_kmh, is_violation, annotated  # Return fallback output.

    # Reshape points to remove the extra dimension for easier math.
    good_prev = good_prev.reshape(-1, 2)  # Shape becomes (N, 2) for x/y.
    good_next = good_next.reshape(-1, 2)  # Shape becomes (N, 2) for x/y.

    # Compute displacement in pixels for each tracked point.
    displacement: np.ndarray = good_next - good_prev  # dx, dy for each point.

    # Compute magnitude (distance) of displacement for each point in pixels.
    displacement_pixels: np.ndarray = np.sqrt(displacement[:, 0] ** 2 + displacement[:, 1] ** 2)  # Euclidean distance in pixels.

    # Take the average displacement per frame in pixels.
    mean_displacement_pixels: float = float(np.mean(displacement_pixels))  # Mean pixel movement across tracked points.

    # Convert pixel displacement to meters using calibration.
    meters_per_frame: float = mean_displacement_pixels / float(pixels_per_meter)  # meters moved during one frame interval.

    # Convert meters-per-frame into meters-per-second using FPS.
    speed_m_per_s: float = meters_per_frame * float(fps)  # Multiply by frames per second to get m/s.

    # Convert meters-per-second into km/h.
    speed_kmh: float = speed_m_per_s * 3.6  # 1 m/s = 3.6 km/h.

    # Flag violation if speed exceeds the limit.
    is_violation: bool = speed_kmh > float(speed_limit_kmh)  # Compare to limit.

    # Decide the color for annotation text:
    # Red for speeding, green for normal speed.
    color = (0, 0, 255) if is_violation else (0, 255, 0)  # BGR format for OpenCV.

    # Draw a background rectangle behind text to keep it readable.
    text: str = f"{speed_kmh:.1f} km/h"  # Text string for annotation.
    (text_w, text_h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)  # Measure text size.
    # Compute rectangle coordinates slightly padded around text.
    rect_x1: int = int(text_origin_x)  # Left of background.
    rect_y1: int = int(max(0, text_origin_y - text_h - baseline))  # Top of background.
    rect_x2: int = int(text_origin_x + text_w + 6)  # Right of background.
    rect_y2: int = int(text_origin_y + 6)  # Bottom of background.
    # Draw the filled background rectangle.
    cv2.rectangle(annotated, (rect_x1, rect_y1), (rect_x2, rect_y2), color, -1)  # -1 means filled rectangle.

    # Draw the text on top of the colored background rectangle in white for contrast.
    cv2.putText(annotated, text, (text_origin_x + 3, text_origin_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)  # Draw text.

    # If requested speed is very high, you might want thicker lines; for now we keep simple.
    # Return the estimated speed, violation flag, and annotated frame.
    return speed_kmh, is_violation, annotated  # Final output to caller.

