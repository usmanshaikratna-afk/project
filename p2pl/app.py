from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
from bson import ObjectId
from pymongo import MongoClient, GEOSPHERE
import uuid
import base64
import cv2
import numpy as np
from PIL import Image
from config import Config

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Initialize MongoDB
client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DBNAME']]

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Create indexes
db.users.create_index('email', unique=True)
db.users.create_index('username', unique=True)
db.road_reports.create_index([('location', GEOSPHERE)])
db.road_reports.create_index('status')
db.road_reports.create_index('severity')
db.road_reports.create_index('created_at')

# User class for Flask-Login
class User:
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.full_name = user_data.get('full_name', '')
        self.role = user_data.get('role', 'citizen')
        self.department = user_data.get('department', '')
        self.phone = user_data.get('phone', '')
        self.avatar = user_data.get('avatar', '')
        self.is_active = user_data.get('is_active', True)
        self.created_at = user_data.get('created_at', datetime.utcnow())
        self.last_login = user_data.get('last_login')
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return self.is_active
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return self.id
    
    def is_authority(self):
        return self.role in ['authority', 'admin']
    
    def is_admin(self):
        return self.role == 'admin'
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

# Utility functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        upload_path = os.path.join(
            app.config['UPLOAD_FOLDER'],
            'reports',
            filename
        )
        
        file.save(upload_path)
        return f"/uploads/reports/{filename}"
    return None

def create_default_users():
    """Create default admin and system users"""
    # Check if admin exists
    admin = db.users.find_one({'email': 'admin@smartroads.com'})
    if not admin:
        admin_data = {
            'username': 'admin',
            'email': 'admin@smartroads.com',
            'password_hash': generate_password_hash('admin123'),
            'full_name': 'System Administrator',
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'is_active': True
        }
        db.users.insert_one(admin_data)
        print("Default admin user created: admin@smartroads.com / admin123")
    
    # Check if system user exists
    system = db.users.find_one({'email': 'system@smartroads.com'})
    if not system:
        system_data = {
            'username': 'system',
            'email': 'system@smartroads.com',
            'password_hash': generate_password_hash('system123'),
            'full_name': 'AI Detection System',
            'role': 'authority',
            'created_at': datetime.utcnow(),
            'is_active': True
        }
        db.users.insert_one(system_data)
        print("System user created for AI detections")

def get_statistics():
    """Get system statistics"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    stats = {
        'total_reports': db.road_reports.count_documents({}),
        'reports_today': db.road_reports.count_documents({'created_at': {'$gte': today}}),
        'pending_reports': db.road_reports.count_documents({'status': 'pending'}),
        'resolved_today': db.road_reports.count_documents({'status': 'resolved', 'resolved_at': {'$gte': today}}),
        'high_priority': db.road_reports.count_documents({'severity': 'high'}),
        'ai_detections': db.camera_detections.count_documents({'timestamp': {'$gte': today}}) if 'camera_detections' in db.list_collection_names() else 0
    }
    
    return stats

# Routes
@app.route('/')
def index():
    stats = get_statistics()
    return render_template('index.html', stats=stats, user=current_user)

@app.route('/about')
def about():
    return render_template('about.html', user=current_user)

@app.route('/map')
def map_page():
    # Get all reports for the map
    reports = list(db.road_reports.find({}).sort('created_at', -1).limit(100))
    
    # Convert ObjectId to string for JSON serialization
    for report in reports:
        report['_id'] = str(report['_id'])
        if 'reporter_id' in report and report['reporter_id']:
            report['reporter_id'] = str(report['reporter_id'])
        if 'assigned_to' in report and report['assigned_to']:
            report['assigned_to'] = str(report['assigned_to'])
    
    return render_template('map.html', reports=reports, user=current_user)

@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    if request.method == 'POST':
        try:
            # Get form data
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            address = request.form.get('address', '')
            issue_type = request.form.get('issue_type')
            severity = request.form.get('severity', 'medium')
            description = request.form.get('description', '')
            
            # Handle file uploads
            images = []
            if 'images' in request.files:
                files = request.files.getlist('images')
                for file in files:
                    if file and file.filename:
                        file_url = save_uploaded_file(file)
                        if file_url:
                            images.append(file_url)
            
            # Create report document
            report_data = {
                'reporter_id': ObjectId(current_user.id),
                'location': {
                    'type': 'Point',
                    'coordinates': [float(longitude), float(latitude)]
                } if latitude and longitude else None,
                'address': address,
                'issue_type': issue_type,
                'severity': severity,
                'description': description,
                'images': images,
                'status': 'pending',
                'priority': 1 if severity == 'high' else 2,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            
            # Insert into database
            result = db.road_reports.insert_one(report_data)
            
            flash('Report submitted successfully!', 'success')
            return redirect(url_for('report'))
            
        except Exception as e:
            flash(f'Error submitting report: {str(e)}', 'danger')
            return redirect(url_for('report'))
    
    return render_template('report.html', user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_authority():
        flash('You need authority access to view the dashboard.', 'warning')
        return redirect(url_for('index'))
    
    # Get dashboard data
    reports = list(db.road_reports.find({}).sort('created_at', -1).limit(50))
    stats = get_statistics()
    
    # Get maintenance teams
    teams = list(db.maintenance_teams.find({})) if 'maintenance_teams' in db.list_collection_names() else []
    
    # Convert ObjectId to string
    for report in reports:
        report['_id'] = str(report['_id'])
    
    for team in teams:
        team['_id'] = str(team['_id'])
    
    return render_template('dashboard.html', 
                         reports=reports, 
                         stats=stats, 
                         teams=teams, 
                         user=current_user)

@app.route('/camera_live')
@login_required
def camera_live():
    if not current_user.is_authority():
        flash('You need authority access to view camera feeds.', 'warning')
        return redirect(url_for('index'))
    
    # Get registered cameras
    cameras = list(db.cameras.find({})) if 'cameras' in db.list_collection_names() else []
    
    # Get recent detections
    detections = list(db.camera_detections.find({}).sort('timestamp', -1).limit(10)) if 'camera_detections' in db.list_collection_names() else []
    
    return render_template('camera_live.html', 
                         cameras=cameras,
                         detections=detections,
                         user=current_user)

@app.route('/contact')
def contact():
    return render_template('contact.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard' if current_user.is_authority() else 'index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user_data = db.users.find_one({'email': email})
        
        if user_data:
            user = User(user_data)
            if user.check_password(password) and user.is_active:
                login_user(user, remember=remember)
                
                # Update last login
                db.users.update_one(
                    {'_id': ObjectId(user.id)},
                    {'$set': {'last_login': datetime.utcnow()}}
                )
                
                flash('Logged in successfully!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard' if user.is_authority() else 'index'))
        
        flash('Invalid email or password', 'danger')
    
    return render_template('login.html', user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name', '')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
        elif db.users.find_one({'email': email}):
            flash('Email already registered', 'danger')
        elif db.users.find_one({'username': username}):
            flash('Username already taken', 'danger')
        else:
            # Create new user
            user_data = {
                'username': username,
                'email': email,
                'password_hash': generate_password_hash(password),
                'full_name': full_name,
                'role': 'citizen',
                'created_at': datetime.utcnow(),
                'is_active': True
            }
            
            db.users.insert_one(user_data)
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html', user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/report/<report_id>')
@login_required
def view_report(report_id):
    try:
        report = db.road_reports.find_one({'_id': ObjectId(report_id)})
        if not report:
            flash('Report not found', 'danger')
            return redirect(url_for('dashboard'))
        
        report['_id'] = str(report['_id'])
        
        # Get reporter info
        if 'reporter_id' in report and report['reporter_id']:
            reporter = db.users.find_one({'_id': ObjectId(report['reporter_id'])})
            report['reporter'] = reporter
        
        return render_template('view_report.html', report=report, user=current_user)
    except:
        flash('Invalid report ID', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/report/<report_id>/update', methods=['POST'])
@login_required
def update_report(report_id):
    if not current_user.is_authority():
        flash('You need authority access to update reports.', 'warning')
        return redirect(url_for('index'))
    
    try:
        status = request.form.get('status')
        assigned_to = request.form.get('assigned_to')
        resolution_notes = request.form.get('resolution_notes', '')
        
        update_data = {'updated_at': datetime.utcnow()}
        
        if status:
            update_data['status'] = status
            if status == 'resolved':
                update_data['resolved_at'] = datetime.utcnow()
                update_data['resolution_notes'] = resolution_notes
        
        if assigned_to:
            update_data['assigned_to'] = ObjectId(assigned_to)
            update_data['assigned_at'] = datetime.utcnow()
            if 'status' not in update_data:
                update_data['status'] = 'assigned'
        
        db.road_reports.update_one(
            {'_id': ObjectId(report_id)},
            {'$set': update_data}
        )
        
        flash('Report updated successfully', 'success')
    except Exception as e:
        flash(f'Error updating report: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/detect', methods=['POST'])
@login_required
def detect_defects():
    if not current_user.is_authority():
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    
    try:
        # Read image
        image = Image.open(file)
        image_np = np.array(image)
        
        # Mock detection (replace with actual AI model)
        # For now, simulate detection
        import random
        
        if random.random() < 0.3:  # 30% chance of detection
            defect_types = ['pothole', 'crack', 'speed_hump', 'debris']
            defect_type = random.choice(defect_types)
            confidence = random.uniform(0.7, 0.95)
            
            height, width = image_np.shape[:2]
            bbox = {
                'x': int(width * random.uniform(0.1, 0.7)),
                'y': int(height * random.uniform(0.1, 0.7)),
                'width': int(width * random.uniform(0.2, 0.4)),
                'height': int(height * random.uniform(0.2, 0.4))
            }
            
            # Draw bounding box
            annotated = image_np.copy()
            cv2.rectangle(annotated, 
                         (bbox['x'], bbox['y']), 
                         (bbox['x'] + bbox['width'], bbox['y'] + bbox['height']), 
                         (0, 255, 0), 3)
            
            # Save annotated image
            detection_id = f"detection_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            filename = f"{detection_id}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'detections', filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            cv2.imwrite(filepath, cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR))
            
            # Save detection record
            detection_data = {
                'camera_id': request.form.get('camera_id', 'unknown'),
                'image_url': f"/uploads/detections/{filename}",
                'detections': [{
                    'type': defect_type,
                    'confidence': confidence,
                    'bbox': bbox
                }],
                'confidence': confidence,
                'processed': True,
                'timestamp': datetime.utcnow()
            }
            
            if 'camera_detections' not in db.list_collection_names():
                db.create_collection('camera_detections')
            
            db.camera_detections.insert_one(detection_data)
            
            return jsonify({
                'detected': True,
                'defect_type': defect_type,
                'confidence': confidence,
                'bbox': bbox,
                'image_url': f"/uploads/detections/{filename}"
            })
        else:
            return jsonify({
                'detected': False,
                'message': 'No defects detected'
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/nearby')
def get_nearby_reports():
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        distance = int(request.args.get('distance', 5000))
        
        query = {
            'location': {
                '$near': {
                    '$geometry': {
                        'type': 'Point',
                        'coordinates': [lon, lat]
                    },
                    '$maxDistance': distance
                }
            }
        }
        
        reports = list(db.road_reports.find(query).limit(50))
        
        # Convert ObjectId to string
        for report in reports:
            report['_id'] = str(report['_id'])
        
        return jsonify({'reports': reports})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        create_default_users()
    
    print("Starting Smart Road Monitor System...")
    print(f"Server running at http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)