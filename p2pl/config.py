import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secret key for session management
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # MongoDB Configuration
    MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_roads'
    MONGO_DBNAME = 'smart_roads'
    
    # File upload configuration
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # ESP32 Camera Configuration
    ESP32_CAM_IP = os.environ.get('ESP32_CAM_IP', '192.168.1.100')
    ESP32_CAM_PORT = int(os.environ.get('ESP32_CAM_PORT', 80))
    
    # Security
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    @staticmethod
    def init_app(app):
        # Create necessary directories
        os.makedirs(os.path.join(basedir, 'uploads', 'reports'), exist_ok=True)
        os.makedirs(os.path.join(basedir, 'uploads', 'detections'), exist_ok=True)
        os.makedirs(os.path.join(basedir, 'ml_models'), exist_ok=True)