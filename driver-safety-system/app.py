from flask import Flask, render_template, Response, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import threading
import time
import json
from datetime import datetime
import os
import base64
from io import BytesIO

# Import custom models
from models.drowsiness_model import DrowsinessDetector

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['TEMPLATES_AUTO_RELOAD'] = True
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize detectors
drowsiness_detector = DrowsinessDetector()

# Global variables for monitoring
monitoring_active = False
current_alert_level = "normal"
driver_data = {
    'drowsiness_level': 0,
    'alcohol_level': 0,
    'eye_status': 'unknown',
    'head_position': 'unknown',
    'alert_status': 'normal',
    'timestamp': None
}

class VideoCamera:
    def __init__(self):
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
    def __del__(self):
        self.video.release()
        
    def get_frame(self):
        success, frame = self.video.read()
        if success:
            # Process frame for drowsiness detection
            processed_frame, data = drowsiness_detector.process_frame(frame)
            
            # Update global driver data
            global driver_data
            driver_data.update({
                'drowsiness_level': data['drowsiness_level'],
                'eye_status': data['eye_status'],
                'head_position': data['head_position'],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Check for alerts
            if data['drowsiness_level'] > 0.7:
                socketio.emit('alert', {'type': 'drowsiness', 'level': 'high'})
            
            # Encode frame for streaming
            ret, jpeg = cv2.imencode('.jpg', processed_frame)
            return jpeg.tobytes()
        return None

camera = None

def generate_frames():
    global camera
    if camera is None:
        camera = VideoCamera()
    
    while True:
        if camera:
            frame = camera.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/monitoring')
def monitoring():
    return render_template('monitoring.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/driver_status')
def driver_status():
    return jsonify(driver_data)

@app.route('/api/alcohol_detection', methods=['POST'])
def alcohol_detection():
    # Simulated alcohol detection
    data = request.json
    simulated_level = np.random.uniform(0, 0.15)
    
    driver_data['alcohol_level'] = simulated_level
    
    if simulated_level > 0.08:
        socketio.emit('alert', {'type': 'alcohol', 'level': 'high'})
        return jsonify({'status': 'danger', 'alcohol_level': simulated_level})
    
    return jsonify({'status': 'safe', 'alcohol_level': simulated_level})

@app.route('/api/simulate_alcohol', methods=['POST'])
def simulate_alcohol():
    """Endpoint to simulate alcohol detection for testing"""
    level = request.json.get('level', 0.05)
    driver_data['alcohol_level'] = level
    
    if level > 0.08:
        socketio.emit('alert', {'type': 'alcohol', 'level': 'high'})
    
    return jsonify({'status': 'success', 'alcohol_level': level})

@app.route('/api/reset', methods=['POST'])
def reset_system():
    """Reset the monitoring system"""
    global driver_data
    driver_data = {
        'drowsiness_level': 0,
        'alcohol_level': 0,
        'eye_status': 'unknown',
        'head_position': 'unknown',
        'alert_status': 'normal',
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    socketio.emit('reset', {'message': 'System reset'})
    return jsonify({'status': 'success'})

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'data': 'Connected to monitoring system'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('start_monitoring')
def handle_start_monitoring():
    global monitoring_active, camera
    monitoring_active = True
    if camera is None:
        camera = VideoCamera()
    emit('monitoring_status', {'status': 'active'})

@socketio.on('stop_monitoring')
def handle_stop_monitoring():
    global monitoring_active, camera
    monitoring_active = False
    if camera:
        camera.__del__()
        camera = None
    emit('monitoring_status', {'status': 'stopped'})

@socketio.on('emergency_stop')
def handle_emergency_stop():
    print("EMERGENCY STOP ACTIVATED")
    emit('alert', {'type': 'emergency', 'level': 'critical'})

if __name__ == '__main__':
    print("Starting Driver Safety System...")
    print("Access the application at http://localhost:5000")
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)