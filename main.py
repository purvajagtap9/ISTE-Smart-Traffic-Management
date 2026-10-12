# main.py
# Master controller for I-STE system
# Runs camera detection + adaptive signal control 24/7
# Works completely in background even when no one is watching

import threading
import time
from datetime import datetime

# ─── Global Shared State ──────────────────────────────────────
camera_urls = {
    "North": "",
    "South": "",
    "East":  "",
    "West":  "",
}

# ─── Camera Setup ─────────────────────────────────────────────
def setup_cameras():
    global camera_urls
    print("\n" + "="*55)
    print("  📱 CAMERA SETUP")
    print("  Format: http://192.168.x.x:8080/video")
    print("  Press Enter to use SIMULATION for that lane.")
    print("="*55 + "\n")

    for lane in ["North", "South", "East", "West"]:
        url = input(f"  Camera URL for {lane} lane: ").strip()
        if url:
            if not url.startswith("http"):
                url = "http://" + url
            if not url.endswith("/video"):
                url = url.rstrip("/") + "/video"
            camera_urls[lane] = url
            print(f"  ✅ {lane} → {url}")
        else:
            camera_urls[lane] = ""
            print(f"  🔄 {lane} → Simulation mode")
    print()

# ─── Adaptive Signal Control Loop ────────────────────────────
def run_adaptive_signal_loop():
    """
    The core adaptive signal control system.

    Logic:
    1. Read vehicle counts from all 4 lanes every cycle
    2. Sort lanes by vehicle count (highest first = priority)
    3. Give GREEN to each lane proportional to its density:
       - High   density → 50 seconds green
       - Medium density → 30 seconds green
       - Low    density → 15 seconds green
       - Zero vehicles  → skip this lane (gap actuation)
    4. Yellow for 3 seconds before switching
    5. All other lanes stay RED while one is GREEN
    6. Repeat cycle continuously 24/7

    This ensures:
    - Every lane gets green time fairly
    - Busier lanes get more green time
    - Empty lanes don't waste time
    - System works with or without admin watching
    """
    from modules.detection_engine import (
        detection_state, state_lock
    )

    LANES      = ["North", "South", "East", "West"]
    YELLOW_SEC = 3
    MIN_GREEN  = 10  # Minimum green even for low density

    print("[SIGNAL] 🚦 Adaptive signal loop started")
    print("[SIGNAL] Logic: High=50s | Medium=30s | Low=15s | Empty=skip")

    def set_all_red():
        """Sets all lanes to RED signal."""
        with state_lock:
            for l in LANES:
                detection_state[l]["signal"]        = "RED"
                detection_state[l]["time_remaining"] = 0
        _sync_signal_module("RED", None)

    def set_lane_green(lane, duration):
        """Sets one lane GREEN, all others RED."""
        with state_lock:
            for l in LANES:
                detection_state[l]["signal"]        = "RED"
                detection_state[l]["time_remaining"] = 0
            detection_state[lane]["signal"]        = "GREEN"
            detection_state[lane]["time_remaining"] = duration
        _sync_signal_module("GREEN", lane, duration)

    def set_lane_yellow(lane):
        """Sets one lane YELLOW before switching."""
        with state_lock:
            detection_state[lane]["signal"]        = "YELLOW"
            detection_state[lane]["time_remaining"] = YELLOW_SEC
        _sync_signal_module("YELLOW", lane)

    def countdown(lane, total_seconds):
        """
        Counts down green time for a lane second by second.
        Updates time_remaining so dashboard shows live countdown.
        Returns False if emergency override needed.
        """
        for remaining in range(total_seconds, 0, -1):
            # Check for emergency override
            try:
                from modules.emergency_detector import any_emergency_active
                if any_emergency_active():
                    return False
            except Exception:
                pass

            with state_lock:
                detection_state[lane]["time_remaining"] = remaining

            # Sync to signal_control module
            try:
                from modules.signal_control import signal_state
                signal_state[lane]["time_remaining"] = remaining
                signal_state[lane]["color"]          = "GREEN"
            except Exception:
                pass

            time.sleep(1)
        return True

    # Start all RED
    set_all_red()

    while True:
        try:
            # ── Step 1: Read current vehicle counts ──────────
            with state_lock:
                lane_data = []
                for lane in LANES:
                    count   = detection_state[lane]["vehicle_count"]
                    density = detection_state[lane]["density"]
                    lane_data.append({
                        "lane":    lane,
                        "count":   count,
                        "density": density,
                    })

            # ── Step 2: Sort by count (highest priority first)
            lane_data.sort(key=lambda x: x["count"], reverse=True)

            # ── Step 3: Calculate green times ────────────────
            total_vehicles = sum(d["count"] for d in lane_data)
            active_lanes   = [d for d in lane_data if d["count"] > 0]

            # If all lanes empty → use default round robin
            if not active_lanes:
                print("[SIGNAL] All lanes empty → default cycle")
                for lane in LANES:
                    set_lane_green(lane, MIN_GREEN)
                    _print_signal_status(lane, 0, "Low", MIN_GREEN)
                    # Countdown
                    for rem in range(MIN_GREEN, 0, -1):
                        with state_lock:
                            detection_state[lane]["time_remaining"] = rem
                        time.sleep(1)
                    set_lane_yellow(lane)
                    time.sleep(YELLOW_SEC)
                    set_all_red()
                continue

            # ── Step 4: Give green to each active lane ───────
            for lane_info in lane_data:
                lane    = lane_info["lane"]
                count   = lane_info["count"]
                density = lane_info["density"]

                # Skip empty lanes (gap actuation)
                if count == 0:
                    print(f"[SIGNAL] ⏭️  {lane} → SKIP (0 vehicles)")
                    continue

                # Calculate green time based on density
                if density == "High":
                    green_time = 50
                elif density == "Medium":
                    green_time = 30
                else:
                    green_time = 15

                # Update green_time in state
                with state_lock:
                    detection_state[lane]["green_time"] = green_time

                # Set this lane GREEN
                set_lane_green(lane, green_time)
                _print_signal_status(lane, count, density, green_time)

                # Count down (returns False if emergency)
                completed = countdown(lane, green_time)

                if not completed:
                    # Emergency detected → handle it
                    print("[SIGNAL] 🚨 Emergency override - pausing cycle")
                    _handle_emergency_override()
                    break

                # Yellow before switching
                set_lane_yellow(lane)
                print(f"[SIGNAL] 🟡 YELLOW → {lane} ({YELLOW_SEC}s)")
                time.sleep(YELLOW_SEC)

                # Back to RED
                with state_lock:
                    detection_state[lane]["signal"]        = "RED"
                    detection_state[lane]["time_remaining"] = 0
                try:
                    from modules.signal_control import signal_state
                    signal_state[lane]["color"]          = "RED"
                    signal_state[lane]["time_remaining"] = 0
                except Exception:
                    pass

            # Small pause between cycles
            time.sleep(1)

        except Exception as e:
            print(f"[SIGNAL ERROR] {e}")
            time.sleep(5)

def _handle_emergency_override():
    """
    Handles emergency vehicle preemption.
    Gives GREEN to emergency lane for 20 seconds.
    Then returns to normal cycle.
    """
    from modules.detection_engine import detection_state, state_lock
    from modules.emergency_detector import (
        get_emergency_lane, any_emergency_active, cancel_emergency
    )

    LANES = ["North", "South", "East", "West"]
    emergency_lane = get_emergency_lane()

    if not emergency_lane:
        return

    print(f"[SIGNAL] 🚨 EMERGENCY GREEN → {emergency_lane}")

    # All RED first
    with state_lock:
        for l in LANES:
            detection_state[l]["signal"]        = "RED"
            detection_state[l]["time_remaining"] = 0

    # Emergency lane GREEN for 20 seconds
    with state_lock:
        detection_state[emergency_lane]["signal"]        = "GREEN"
        detection_state[emergency_lane]["time_remaining"] = 20

    # Wait for emergency to clear
    for i in range(20):
        if not any_emergency_active():
            break
        with state_lock:
            detection_state[emergency_lane]["time_remaining"] = 20 - i
        time.sleep(1)

    # Back to RED
    with state_lock:
        detection_state[emergency_lane]["signal"]        = "RED"
        detection_state[emergency_lane]["time_remaining"] = 0

    print("[SIGNAL] ✅ Emergency cleared - resuming normal cycle")

def _sync_signal_module(color, green_lane, duration=0):
    """
    Keeps signal_control.py in sync with detection_engine.
    This ensures admin signal control page shows correct data.
    """
    try:
        from modules.signal_control import signal_state
        LANES = ["North", "South", "East", "West"]
        for lane in LANES:
            if lane == green_lane and color == "GREEN":
                signal_state[lane]["color"]          = "GREEN"
                signal_state[lane]["time_remaining"] = duration
            elif lane == green_lane and color == "YELLOW":
                signal_state[lane]["color"]          = "YELLOW"
                signal_state[lane]["time_remaining"] = 3
            else:
                signal_state[lane]["color"]          = "RED"
                signal_state[lane]["time_remaining"] = 0
    except Exception:
        pass

def _print_signal_status(lane, count, density, green_time):
    """Prints formatted signal status to terminal."""
    emoji = "🟢"
    print(f"\n[SIGNAL] {emoji} GREEN → {lane}")
    print(f"         Vehicles : {count}")
    print(f"         Density  : {density}")
    print(f"         Green    : {green_time}s")
    print(f"         Time     : {datetime.now().strftime('%H:%M:%S')}")

# ─── Document Check Loop ─────────────────────────────────────
def run_document_check_loop():
    """
    Checks all vehicle documents every hour.
    Sends email+SMS alerts for expiring documents.
    """
    print("[DOCS] Document check loop started")
    time.sleep(60)  # Wait 1 min after startup

    while True:
        try:
            from app import create_app
            app = create_app()
            with app.app_context():
                _check_documents()
        except Exception as e:
            print(f"[DOCS ERROR] {e}")
        time.sleep(3600)  # Every hour

def _check_documents():
    from datetime import timedelta
    from models.vehicle_model import Vehicle
    from models.user_model    import User
    from modules.notification_service import send_document_expiry_alert

    now  = datetime.utcnow()
    soon = now + timedelta(days=30)

    try:
        vehicles = Vehicle.query.all()
        for vehicle in vehicles:
            owner = User.query.get(vehicle.owner_id)
            if not owner:
                continue
            docs = {
                "PUC":       vehicle.puc_expiry_date,
                "Insurance": vehicle.insurance_expiry_date,
                "RC":        vehicle.rc_expiry_date,
            }
            for doc_name, expiry in docs.items():
                if expiry and now < expiry < soon:
                    days_left = (expiry - now).days
                    print(f"[DOCS] ⚠️ {vehicle.plate_number} "
                          f"{doc_name} expires in {days_left}d")
                    send_document_expiry_alert(
                        driver_name    = owner.full_name,
                        email          = owner.email,
                        phone          = owner.phone_number,
                        plate          = vehicle.plate_number,
                        doc_type       = doc_name,
                        expiry_date    = expiry,
                        days_remaining = days_left,
                    )
    except Exception as e:
        print(f"[DOCS] Query error: {e}")

# ─── Status Printer ───────────────────────────────────────────
def run_status_printer():
    """Prints live system status every 15 seconds."""
    while True:
        time.sleep(15)
        try:
            from modules.detection_engine import detection_state, state_lock
            print("\n" + "="*68)
            print(f"  I-STE LIVE STATUS | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*68)
            print(f"  {'LANE':<8} {'VEHICLES':<10} {'DENSITY':<10} "
                  f"{'SIGNAL':<10} {'GREEN':<8} {'CAMERA'}")
            print("-"*68)
            with state_lock:
                for lane, data in detection_state.items():
                    sig   = data["signal"]
                    emoji = ("🟢" if sig=="GREEN"
                             else "🟡" if sig=="YELLOW"
                             else "🔴")
                    cam   = "📹 Live" if data["camera_on"] else "🔄 Sim"
                    print(f"  {lane:<8} {data['vehicle_count']:<10} "
                          f"{data['density']:<10} "
                          f"{emoji} {sig:<8} "
                          f"{data['green_time']}s{'':<4} {cam}")
            print("="*68 + "\n")
        except Exception:
            pass

# ─── Main Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  🚦 I-STE SMART TRAFFIC ENGINEERING SYSTEM")
    print("  Adaptive Signal Control | 24/7 Autonomous")
    print("="*55)

    # Step 1: Camera setup
    setup_cameras()

    # Step 2: Start camera manager
    print("[MAIN] 📹 Starting camera manager...")
    try:
        from modules.camera_manager import start_camera_manager
        start_camera_manager(camera_urls)
        time.sleep(2)
        print("[MAIN] ✅ Camera manager ready")
    except Exception as e:
        print(f"[MAIN] Camera manager error: {e}")

    # Step 3: Start detection engine
    print("[MAIN] 🧠 Starting detection engine...")
    try:
        from modules.detection_engine import start_engine, update_camera_url
        start_engine()
        # Register initial camera URLs with engine
        for lane, url in camera_urls.items():
            if url:
                update_camera_url(lane, url)
        time.sleep(2)
        print("[MAIN] ✅ Detection engine ready")
    except Exception as e:
        print(f"[MAIN] Detection engine error: {e}")

    # Step 4: Start adaptive signal loop (background)
    signal_thread = threading.Thread(
        target = run_adaptive_signal_loop,
        name   = "AdaptiveSignal",
        daemon = True
    )
    signal_thread.start()
    print("[MAIN] ✅ Adaptive signal control started (background)")

    # Step 5: Start document check loop (background)
    doc_thread = threading.Thread(
        target = run_document_check_loop,
        name   = "DocChecker",
        daemon = True
    )
    doc_thread.start()
    print("[MAIN] ✅ Document checker started (background)")

    # Step 6: Start status printer (background)
    status_thread = threading.Thread(
        target = run_status_printer,
        name   = "StatusPrinter",
        daemon = True
    )
    status_thread.start()

    # Step 7: Start Flask web server
    print("\n[MAIN] 🌐 Starting web dashboard...")
    print("[MAIN] URL   : http://localhost:5000")
    print("[MAIN] Admin : admin@iste.com / admin123")
    print("[MAIN] User  : rahul@example.com / user123")
    print("[MAIN] Press Ctrl+C to stop\n")

    try:
        from app import create_app
        app = create_app()
        app.run(
            debug        = False,
            host         = "0.0.0.0",
            port         = 5000,
            use_reloader = False,
            threaded     = True,
        )
    except KeyboardInterrupt:
        print("\n[MAIN] 🛑 System stopped by user")