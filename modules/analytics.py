# analytics.py
# This module analyzes traffic data and generates reports
# It reads log files and CSV files to produce statistics
# Results are shown on the admin analytics dashboard

import csv
import os
from datetime import datetime, timedelta
from collections import Counter

# ─── File Paths ──────────────────────────────────────────────
# These are the log files created by other modules
VIOLATIONS_CSV   = "violations_log.csv"
EMERGENCY_LOG    = "emergency_log.txt"
FAULT_LOG        = "fault_log.txt"
DAILY_REPORT     = "daily_report.txt"

# ─── Helper: Check if File Exists ────────────────────────────
def file_exists(filepath):
    """
    Checks if a file exists before trying to read it.
    Returns True if file exists, False otherwise.
    """
    return os.path.exists(filepath)

# ─── Read Violations CSV ──────────────────────────────────────
def read_violations():
    """
    Reads all violations from violations_log.csv
    Returns a list of dictionaries, one per violation.
    Returns empty list if file doesn't exist yet.
    """
    violations = []

    # Check if file exists first
    if not file_exists(VIOLATIONS_CSV):
        return violations

    try:
        with open(VIOLATIONS_CSV, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                violations.append(row)
    except Exception as e:
        print(f"[ANALYTICS] Error reading violations: {e}")

    return violations

# ─── Total Violations Count ───────────────────────────────────
def get_total_violations():
    """
    Returns total number of violations recorded.
    """
    return len(read_violations())

# ─── Violations by Type ───────────────────────────────────────
def get_violations_by_type():
    """
    Counts violations grouped by type.
    Example: {"speeding": 10, "signal": 5, "document": 3}
    """
    violations = read_violations()

    # Get just the violation_type column from each row
    types = [v.get("violation_type", "unknown") for v in violations]

    # Count occurrences of each type
    return dict(Counter(types))

# ─── Most Common Violation ────────────────────────────────────
def get_most_common_violation():
    """
    Returns the most frequently occurring violation type.
    """
    by_type = get_violations_by_type()

    if not by_type:
        return "No violations recorded"

    # Find the type with highest count
    return max(by_type, key=by_type.get)

# ─── Violations by Lane ───────────────────────────────────────
def get_violations_by_lane():
    """
    Counts violations grouped by lane.
    Example: {"North": 5, "South": 3, "East": 7, "West": 2}
    """
    violations = read_violations()
    lanes = [v.get("lane", "unknown") for v in violations]
    return dict(Counter(lanes))

# ─── Peak Violation Hour ──────────────────────────────────────
def get_peak_violation_hour():
    """
    Finds the hour of day with most violations.
    Returns hour as integer (0-23).
    """
    violations = read_violations()

    if not violations:
        return "No data"

    hours = []
    for v in violations:
        try:
            # Parse timestamp and extract hour
            timestamp = v.get("timestamp", "")
            if timestamp:
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                hours.append(dt.hour)
        except Exception:
            continue

    if not hours:
        return "No data"

    # Find most common hour
    peak_hour = Counter(hours).most_common(1)[0][0]
    return f"{peak_hour}:00 - {peak_hour+1}:00"

# ─── Total Fines Collected ────────────────────────────────────
def get_total_fines():
    """
    Calculates total fine amount from all violations.
    Returns total as float.
    """
    violations = read_violations()
    total = 0.0

    for v in violations:
        try:
            amount = float(v.get("fine_amount", 0))
            total += amount
        except Exception:
            continue

    return total

# ─── Paid vs Unpaid Fines ─────────────────────────────────────
def get_paid_unpaid_fines():
    """
    Separates fines into paid and unpaid amounts.
    Returns dict: {"paid": amount, "unpaid": amount}
    """
    violations = read_violations()
    paid   = 0.0
    unpaid = 0.0

    for v in violations:
        try:
            amount    = float(v.get("fine_amount", 0))
            is_paid   = v.get("is_paid", "False")

            if is_paid == "True":
                paid += amount
            else:
                unpaid += amount
        except Exception:
            continue

    return {"paid": paid, "unpaid": unpaid}

# ─── Violations Per Hour (for Chart) ─────────────────────────
def get_violations_per_hour():
    """
    Returns violation counts for each hour of today.
    Used by Chart.js line chart on analytics page.
    Returns list of 24 values (one per hour).
    """
    violations = read_violations()

    # Initialize all 24 hours to 0
    hourly = [0] * 24

    today = datetime.now().date()

    for v in violations:
        try:
            timestamp = v.get("timestamp", "")
            if timestamp:
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                # Only count today's violations
                if dt.date() == today:
                    hourly[dt.hour] += 1
        except Exception:
            continue

    return hourly

# ─── Read Emergency Log ───────────────────────────────────────
def get_total_emergencies():
    """
    Counts total emergency events from emergency_log.txt
    Returns integer count.
    """
    if not file_exists(EMERGENCY_LOG):
        return 0

    try:
        with open(EMERGENCY_LOG, "r") as f:
            # Each line is one emergency event
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return len(lines)
    except Exception as e:
        print(f"[ANALYTICS] Error reading emergency log: {e}")
        return 0

# ─── Emergencies Per Day (for Chart) ─────────────────────────
def get_emergencies_per_day():
    """
    Returns emergency counts for last 7 days.
    Used by Chart.js on analytics dashboard.
    Returns dict: {"2026-04-01": 2, "2026-03-31": 1, ...}
    """
    if not file_exists(EMERGENCY_LOG):
        return {}

    daily_counts = {}

    try:
        with open(EMERGENCY_LOG, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    # Format: "2026-04-01 12:30:00 | Lane: North | ..."
                    date_str = line.split(" ")[0]
                    if date_str in daily_counts:
                        daily_counts[date_str] += 1
                    else:
                        daily_counts[date_str] = 1
                except Exception:
                    continue
    except Exception as e:
        print(f"[ANALYTICS] Error reading emergency log: {e}")

    return daily_counts

# ─── Read Fault Log ───────────────────────────────────────────
def get_total_faults():
    """
    Counts total sensor faults from fault_log.txt
    Returns integer count.
    """
    if not file_exists(FAULT_LOG):
        return 0

    try:
        with open(FAULT_LOG, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return len(lines)
    except Exception as e:
        print(f"[ANALYTICS] Error reading fault log: {e}")
        return 0

# ─── Vehicle Count Per Lane (for Chart) ──────────────────────
def get_vehicle_counts_per_lane(live_counts=None):
    """
    Returns current vehicle counts per lane.
    live_counts: optional dict from camera system
    If no live data, returns simulated counts.
    """
    if live_counts:
        return live_counts

    # Return simulated data if no live camera connected
    import random
    return {
        "North": random.randint(0, 15),
        "South": random.randint(0, 15),
        "East":  random.randint(0, 15),
        "West":  random.randint(0, 15),
    }

# ─── Generate Daily Report ────────────────────────────────────
def generate_daily_report():
    """
    Creates a text summary report of today's traffic activity.
    Saves to daily_report.txt file.
    Also returns report as string for display.
    """
    today     = datetime.now().strftime("%Y-%m-%d")
    now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Gather all statistics
    total_violations   = get_total_violations()
    most_common        = get_most_common_violation()
    peak_hour          = get_peak_violation_hour()
    total_fines        = get_total_fines()
    paid_unpaid        = get_paid_unpaid_fines()
    total_emergencies  = get_total_emergencies()
    total_faults       = get_total_faults()
    by_lane            = get_violations_by_lane()
    by_type            = get_violations_by_type()

    # Build report string
    report = f"""
╔══════════════════════════════════════════════╗
║         I-STE DAILY TRAFFIC REPORT           ║
║              Date: {today}              ║
╚══════════════════════════════════════════════╝

Generated at: {now}

── VIOLATIONS SUMMARY ──────────────────────────
  Total Violations    : {total_violations}
  Most Common Type    : {most_common}
  Peak Violation Hour : {peak_hour}

── FINES SUMMARY ───────────────────────────────
  Total Fines Issued  : Rs. {total_fines:.2f}
  Fines Collected     : Rs. {paid_unpaid['paid']:.2f}
  Fines Pending       : Rs. {paid_unpaid['unpaid']:.2f}

── VIOLATIONS BY LANE ──────────────────────────
"""
    for lane, count in by_lane.items():
        report += f"  {lane:<10} : {count} violations\n"

    report += "\n── VIOLATIONS BY TYPE ──────────────────────────\n"
    for vtype, count in by_type.items():
        report += f"  {vtype:<15} : {count}\n"

    report += f"""
── SYSTEM EVENTS ───────────────────────────────
  Emergency Events    : {total_emergencies}
  Sensor Faults       : {total_faults}

────────────────────────────────────────────────
  Report auto-generated by I-STE System
────────────────────────────────────────────────
"""

    # Save report to file
    try:
        with open(DAILY_REPORT, "w") as f:
            f.write(report)
        print(f"[ANALYTICS] Daily report saved to {DAILY_REPORT}")
    except Exception as e:
        print(f"[ANALYTICS] Error saving report: {e}")

    return report

# ─── Get Full Analytics Summary ──────────────────────────────
def get_analytics_summary(live_counts=None):
    """
    Returns all analytics data in one dictionary.
    Used by Flask /admin/analytics route to populate dashboard.
    live_counts: optional real-time vehicle counts from cameras
    """
    return {
        "total_violations":    get_total_violations(),
        "violations_by_type":  get_violations_by_type(),
        "violations_by_lane":  get_violations_by_lane(),
        "most_common":         get_most_common_violation(),
        "peak_hour":           get_peak_violation_hour(),
        "total_fines":         get_total_fines(),
        "paid_unpaid":         get_paid_unpaid_fines(),
        "violations_per_hour": get_violations_per_hour(),
        "total_emergencies":   get_total_emergencies(),
        "emergencies_per_day": get_emergencies_per_day(),
        "total_faults":        get_total_faults(),
        "vehicle_counts":      get_vehicle_counts_per_lane(live_counts),
    }