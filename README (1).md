# 🚦 I-STE – Intelligent Smart Traffic Engineering System

An AI-driven Smart Traffic Management System designed to monitor vehicle movement, analyze traffic density, and optimize traffic signal timing using computer vision.

The system aims to improve traffic flow, reduce unnecessary waiting time, and support emergency vehicle prioritization through an intelligent traffic monitoring platform.

**Repository:** [I-STE Smart Traffic Management](https://github.com/purvajagtap9/ISTE-Smart-Traffic-Management)

---

## 📌 Project Overview

Traditional traffic signals generally operate with fixed time intervals, regardless of the number of vehicles waiting on each road.

I-STE addresses this problem by using vehicle detection and traffic-density analysis to support adaptive signal control.

The system provides a web-based interface for administrators and users, along with camera-based traffic monitoring and signal management modules.

## ✨ Key Features

- **Vehicle Detection:** Uses computer vision and YOLO-based detection modules to identify vehicles.
- **Traffic Density Analysis:** Monitors vehicle counts across different traffic lanes.
- **Adaptive Traffic Signals:** Allocates green signal time according to traffic density.
- **Emergency Vehicle Detection:** Includes an emergency detection and priority module.
- **Speed Detection:** Includes a module for vehicle speed monitoring.
- **Violation Detection:** Supports traffic violation monitoring.
- **Number Plate Recognition:** Includes an ANPR module.
- **Admin Dashboard:** Provides administrative monitoring and management features.
- **User Dashboard:** Provides user-facing traffic and vehicle-related functionality.
- **Camera and Simulation Support:** Supports camera inputs and simulation mode.

## 🛠️ Technology Stack

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Backend Framework | Flask |
| Computer Vision | OpenCV |
| Object Detection | YOLOv8 |
| Database | SQLite |
| ORM | Flask-SQLAlchemy / SQLAlchemy |
| Frontend | HTML, CSS, JavaScript |
| Development Tools | VS Code, Git, GitHub |

## 🏗️ Project Architecture

```text
ISTE-Smart-Traffic-Management/
│
├── app/
│   ├── admin/
│   ├── api/
│   ├── auth/
│   ├── user/
│   ├── templates/
│   ├── config.py
│   ├── extensions.py
│   └── __init__.py
│
├── auth/
│
├── models/
│   ├── database.py
│   ├── user_model.py
│   ├── vehicle_model.py
│   ├── violation_model.py
│   └── emergency_log_model.py
│
├── modules/
│   ├── camera_manager.py
│   ├── detection_engine.py
│   ├── vehicle_detector.py
│   ├── emergency_detector.py
│   ├── speed_detector.py
│   ├── anpr.py
│   ├── violation_detector.py
│   ├── signal_control.py
│   └── analytics.py
│
├── main.py
├── run.py
├── env.example
└── README.md
```

## 🔄 System Workflow

1. The system initializes the traffic monitoring application.
2. Camera inputs are configured for North, South, East, and West lanes.
3. If a camera URL is not provided, the corresponding lane can use simulation mode.
4. The detection engine processes traffic input and identifies vehicles.
5. Vehicle counts and traffic density are analyzed.
6. The adaptive signal controller assigns green-light durations according to traffic density.
7. Emergency vehicle detection and priority modules support emergency handling.
8. The Flask dashboard provides traffic monitoring and administrative information.

## 🚀 Installation and Setup

### Prerequisites

- Python installed
- pip package manager
- Git
- VS Code or another Python IDE

### 1. Clone the repository

```bash
git clone https://github.com/purvajagtap9/ISTE-Smart-Traffic-Management.git

cd ISTE-Smart-Traffic-Management
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows:**

```bash
venv\Scripts\activate
```

### 4. Install dependencies

If the project contains a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 5. Run the complete system

```bash
python main.py
```

The system starts its camera configuration, detection engine, adaptive signal controller, and Flask dashboard.

Open the browser:

```text
http://localhost:5000
```

**Dashboard-only mode:**

```bash
python run.py
```

## 🎯 Expected Outcomes

- Improved traffic monitoring through vehicle detection.
- Dynamic signal timing based on traffic density.
- Reduced unnecessary waiting at less congested lanes.
- Support for emergency vehicle prioritization.
- Centralized monitoring through a web-based dashboard.

## 🔮 Future Enhancements

- Integration with real-world traffic signal hardware.
- Advanced traffic prediction using machine learning.
- Improved real-time camera monitoring.
- Enhanced violation reporting and analytics.
- Cloud-based traffic monitoring and data storage.

## 👩‍💻 Project Contribution

Developed as a collaborative engineering project. My contribution included backend development, application modules, and integration of traffic monitoring functionality.

## 📄 Intellectual Property

This project is associated with a patent application. The repository does not grant an open-source license unless explicitly stated.

---

**Developed as part of the I-STE Smart Traffic Management project.**
