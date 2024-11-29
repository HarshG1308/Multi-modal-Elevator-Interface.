# Voice-Activated Elevator Interface

## Overview

This project implements a multi-modal elevator interface using voice control, eye tracking, and traditional mouse input. It's designed to simulate an elevator control panel with various interaction methods, providing a platform for research and demonstration of human-computer interaction techniques.

## Features

- Multiple interaction modalities:
  - Mouse Control
  - Voice Control
  - Eye Tracking (requires Tobii Eye Tracker)
  - Touch Control (if available)
- Simulated elevator functions:
  - Floor selection
  - Door open/close
  - Emergency button
- Real-time feedback and status updates
- Metrics collection for interaction analysis

## Prerequisites

- Python 3.7 or higher
- Tobii Eye Tracker (optional, for eye tracking functionality)
- Windows, macOS, or Linux operating system

## Installation

1. Open the source code in VS Code with python 3.10.10 version.

2. Create and activate a virtual environment (recommended):
    python -m venv venv
    source venv/bin/activate  # On Windows, use venv\Scripts\activate

3. Install the required packages: pip install requirements.txt

4. Download and set up the Vosk model:
- Visit https://alphacephei.com/vosk/models
- Download the English model (e.g., `vosk-model-en-in-0.5`)
- Extract the downloaded model to a folder named `vosk-model-en-in-0.5` in the `Lift Interface/code/` directory

## Running the Application

1. Ensure you're in the project directory and your virtual environment is activated.

2. Run the application: python elevator_interface.py

3. The elevator interface window should appear on your screen.

## Using the Interface

1. Select an interaction modality from the dropdown menu at the top of the interface:
- Mouse Control: Use your mouse to click buttons
- Voice Control: Speak commands like "Floor 3" or "Open door"
- Eye Tracking: Look at buttons for a few seconds to select them (requires Tobii Eye Tracker)
- Touch Control: Use touch input if available on your device
- ALL: Enables all available modalities simultaneously

2. Interact with the elevator interface using the selected modality:
- Click or look at floor buttons to select a destination
- Use the "Open Door" and "Close Door" buttons to control the elevator doors
- The "Emergency" button simulates an emergency stop

3. Observe the interface for real-time updates:
- Current floor indicator
- Door status (Open/Closed)
- Movement direction arrow

4. For voice control, speak clearly and use simple commands:
- "Floor [number]" (e.g., "Floor 5")
- "Open door"
- "Close door"
- "Emergency"

5. Metrics about your interactions will be automatically saved to `Lift Interface/data_collected/elevator_metrics.csv` for later analysis.

## Troubleshooting

- PyAudio installation issues:
- On Ubuntu/Debian: `sudo apt-get install portaudio19-dev`
- On macOS with Homebrew: `brew install portaudio`

- Eye tracking not working:
- Ensure your Tobii Eye Tracker is properly connected via USB
- Check if the Tobii Eye Tracker software is installed and running
- Verify that your system recognizes the eye tracker in device manager

- Voice recognition problems:
- Check your microphone settings and permissions
- Ensure you're in a quiet environment
- Speak clearly and at a normal pace

- Vosk model issues:
- Double-check the model folder name and location
- Try downloading a different version of the model if problems persist

## Data Collection and Privacy

This application collects interaction data for research purposes. The data is stored locally on your machine and is not transmitted over the internet. To view or delete the collected data, check the `Lift Interface/data_collected/elevator_metrics.csv` file.

## Acknowledgments

- [Vosk](https://github.com/alphacep/vosk-api) for speech recognition
- [Tobii Research](https://www.tobiipro.com/) for eye tracking capabilities
- All contributors and testers who have helped improve this project

## Disclaimer

This application is designed for research and demonstration purposes only. It simulates an elevator interface and does not control an actual elevator. Always follow proper safety protocols when using real elevators.