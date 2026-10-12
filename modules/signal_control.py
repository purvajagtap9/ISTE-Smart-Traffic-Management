# signal_control.py
# This module controls traffic signals for all 4 lanes
# It dynamically adjusts green time based on vehicle density
# It also handles emergency overrides and manual control

import time
import threading
from datetime import datetime

# ─── Signal Configuration ────────────────────────────────────
# Green time in seconds based on traffic density
GREEN_TIME = {
    "Low":    15,  # 0-3 vehicles
    "Medium": 30,  # 4-8 vehicles
    "High":   50,  # 9+ vehicles
}

# Yellow light duration (seconds)
YELLOW_TIME = 3

# Minimum green time even if no vehicles (seconds)
MIN_GREEN_TIME = 10

# All lane names
LANES = ["North", "South", "East", "West"]

# ─── Global Signal State ─────────────────────────────────────
# Stores current signal color for each lane
signal_state = {
    "North": {"color": "RED",   "time_remaining": 0, "manual_override": False},
    "South": {"color": "RED",   "time_remaining": 0, "manual_override": False},
    "East":  {"color": "RED",   "time_remaining": 0, "manual_override": False},
    "West":  {"color": "RED",   "time_remaining": 0, "manual_override": False},
}

# Stores the current signal schedule (order of lanes)
current_schedule = []

# Is the signal system running?
is_running = False

# Is manual mode active for any lane?
manual_mode = False

# ─── Calculate Green Time for a Lane ─────────────────────────
def calculate_green_time(density_level):
    """
    Returns green time in seconds based on density level.
    density_level: "Low", "Medium", or "High"
    """
    # Look up green time from dictionary
    return GREEN_TIME.get(density_level, MIN_GREEN_TIME)

# ─── Build Signal Schedule ────────────────────────────────────
def build_schedule(detection_results):
    """
    Creates an ordered list of lanes with their green times.
    Highest density lanes go first (priority scheduling).
    detection_results: dictionary from vehicle_detector.py
    Returns: list of dicts with lane, green_time, vehicle_count
    """
    schedule = []

    for lane, results in detection_results.items():
        # Get vehicle count and density from detection results
        vehicle_count = results.get("vehicle_count", 0)
        density = results.get("density", "Low")

        # Skip lane if no vehicles detected (gap actuation)
        if vehicle_count == 0:
            print(f"[SIGNAL] {lane} lane empty - skipping (gap actuation)")
            continue

        # Calculate green time for this lane
        green_time = calculate_green_time(density)

        # Add lane to schedule
        schedule.append({
            "lane":          lane,
            "green_time":    green_time,
            "vehicle_count": vehicle_count,
            "density":       density,
        })

    # Sort schedule: highest vehicle count goes first (priority)
    schedule.sort(key=lambda x: x["vehicle_count"], reverse=True)

    # If all lanes are empty, use default equal schedule
    if not schedule:
        print("[SIGNAL] All lanes empty - using default schedule")
        for lane in LANES:
            schedule.append({
                "lane":          lane,
                "green_time":    MIN_GREEN_TIME,
                "vehicle_count": 0,
                "density":       "Low",
            })

    return schedule

# ─── Run One Signal Cycle ────────────────────────────────────
def run_signal_cycle(schedule):
    """
    Executes one full signal cycle based on the schedule.
    Gives green to each lane one by one.
    All other lanes stay RED while one is GREEN.
    """
    global signal_state

    for item in schedule:
        lane      = item["lane"]
        green_time = item["green_time"]

        # Check if this lane has manual override - skip if so
        if signal_state[lane]["manual_override"]:
            print(f"[SIGNAL] {lane} has manual override - skipping auto control")
            continue

        # Set all lanes to RED first
        for l in LANES:
            signal_state[l]["color"] = "RED"
            signal_state[l]["time_remaining"] = 0

        # Set current lane to GREEN
        signal_state[lane]["color"] = "GREEN"
        signal_state[lane]["time_remaining"] = green_time

        # Print status
        print(f"\n[SIGNAL] 🟢 GREEN → {lane} lane")
        print(f"         Vehicles: {item['vehicle_count']} | "
              f"Density: {item['density']} | "
              f"Green time: {green_time}s")

        # Count down the green time (update every second)
        for remaining in range(green_time, 0, -1):
            signal_state[lane]["time_remaining"] = remaining
            time.sleep(1)

            # Check if emergency override needed - stop cycle immediately
            from modules.emergency_detector import any_emergency_active, get_emergency_lane
            if any_emergency_active():
                emergency_lane = get_emergency_lane()
                print(f"\n🚨 EMERGENCY OVERRIDE! Switching to {emergency_lane}")
                handle_emergency_override(emergency_lane)
                return  # Stop current cycle

        # Yellow light before switching
        signal_state[lane]["color"] = "YELLOW"
        signal_state[lane]["time_remaining"] = YELLOW_TIME
        print(f"[SIGNAL] 🟡 YELLOW → {lane} lane ({YELLOW_TIME}s)")
        time.sleep(YELLOW_TIME)

        # Set back to RED after yellow
        signal_state[lane]["color"] = "RED"
        signal_state[lane]["time_remaining"] = 0

# ─── Handle Emergency Override ───────────────────────────────
def handle_emergency_override(emergency_lane):
    """
    Immediately gives GREEN to emergency lane.
    All other lanes set to RED.
    Waits for emergency to clear then resumes normal operation.
    """
    global signal_state

    # Set all lanes to RED
    for lane in LANES:
        signal_state[lane]["color"] = "RED"
        signal_state[lane]["time_remaining"] = 0

    # Give GREEN to emergency lane
    signal_state[emergency_lane]["color"] = "GREEN"
    signal_state[emergency_lane]["time_remaining"] = 20

    print(f"\n🚨 EMERGENCY GREEN CORRIDOR → {emergency_lane} lane")
    print("   All other lanes → RED")

    # Wait for emergency to clear (check every second)
    from modules.emergency_detector import any_emergency_active
    for i in range(20):
        if not any_emergency_active():
            print("✅ Emergency cleared - resuming normal signal cycle")
            break
        time.sleep(1)

    # Reset emergency lane back to RED
    signal_state[emergency_lane]["color"] = "RED"

# ─── Manual Override Functions ───────────────────────────────
def set_manual_green(lane_name, duration=30):
    """
    Manually sets a lane to GREEN for a specific duration.
    Used by admin dashboard signal control page.
    lane_name: which lane to set green
    duration: how many seconds to keep it green
    """
    if lane_name not in LANES:
        return {"error": f"Invalid lane: {lane_name}"}

    # Enable manual override for this lane
    signal_state[lane_name]["manual_override"] = True
    signal_state[lane_name]["color"] = "GREEN"
    signal_state[lane_name]["time_remaining"] = duration

    print(f"[MANUAL] Admin set {lane_name} → GREEN for {duration}s")

    # Start timer to release manual override after duration
    def release_override():
        time.sleep(duration)
        signal_state[lane_name]["manual_override"] = False
        signal_state[lane_name]["color"] = "RED"
        signal_state[lane_name]["time_remaining"] = 0
        print(f"[MANUAL] {lane_name} manual override released")

    # Run in background thread so it doesn't block
    t = threading.Thread(target=release_override)
    t.daemon = True
    t.start()

    return {"success": True, "lane": lane_name, "duration": duration}

def release_all_overrides():
    """
    Releases all manual overrides and returns to auto mode.
    Used when admin clicks 'Return to Auto' button.
    """
    for lane in LANES:
        signal_state[lane]["manual_override"] = False
    print("[SIGNAL] All manual overrides released - auto mode active")

# ─── Get Current Signal Status ───────────────────────────────
def get_signal_status():
    """
    Returns current signal colors and timings for all lanes.
    Used by Flask dashboard to show live signal status.
    """
    return signal_state

# ─── Get Signal Color for One Lane ───────────────────────────
def get_lane_signal(lane_name):
    """
    Returns signal color for a specific lane.
    Returns "RED" if lane not found (safe default).
    """
    if lane_name in signal_state:
        return signal_state[lane_name]["color"]
    return "RED"

# ─── Print Signal Status Table ───────────────────────────────
def print_signal_table():
    """
    Prints a formatted table of all lane signals in terminal.
    Useful for monitoring during development and demo.
    """
    print("\n" + "="*55)
    print(f"  {'LANE':<10} {'SIGNAL':<10} {'TIME LEFT':<15} {'OVERRIDE'}")
    print("="*55)
    for lane, state in signal_state.items():
        color    = state["color"]
        time_rem = state["time_remaining"]
        override = "MANUAL" if state["manual_override"] else "AUTO"

        # Add color emoji for readability
        emoji = "🟢" if color == "GREEN" else ("🟡" if color == "YELLOW" else "🔴")
        print(f"  {lane:<10} {emoji} {color:<8} {str(time_rem)+'s':<15} {override}")
    print("="*55 + "\n")