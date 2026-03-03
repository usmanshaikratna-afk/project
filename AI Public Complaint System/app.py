from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import pickle
import numpy as np
import os
import re
import random
import json
import hashlib
from werkzeug.utils import secure_filename
from email.utils import parseaddr
import secrets

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['MAX_FILES_PER_COMPLAINT'] = 5
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mov', 'avi'}

# Initialize database
db = SQLAlchemy(app)
CORS(app)

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class Department(db.Model):
    """Department model"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    head = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    description = db.Column(db.Text)
    total_complaints = db.Column(db.Integer, default=0)
    resolved_complaints = db.Column(db.Integer, default=0)
    pending_complaints = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float, default=0.0)
    avg_resolution_time = db.Column(db.Float, default=0.0)
    satisfaction_rate = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    complaints = db.relationship('Complaint', backref='department_rel', lazy=True)
    officers = db.relationship('Officer', backref='department_rel', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'head': self.head,
            'email': self.email,
            'phone': self.phone,
            'total_complaints': self.total_complaints,
            'resolved_complaints': self.resolved_complaints,
            'pending_complaints': self.pending_complaints,
            'avg_response_time': self.avg_response_time,
            'avg_resolution_time': self.avg_resolution_time,
            'satisfaction_rate': self.satisfaction_rate
        }


class Officer(db.Model):
    """Department officer model"""
    __tablename__ = 'officers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    designation = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    is_active = db.Column(db.Boolean, default=True)
    assigned_complaints = db.Column(db.Integer, default=0)
    resolved_complaints = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Complaint(db.Model):
    """Complaint model"""
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Citizen Information
    citizen_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    alternate_phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    
    # Complaint Details
    complaint_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), index=True)
    subcategory = db.Column(db.String(50))
    priority = db.Column(db.String(20), default='Medium', index=True)
    status = db.Column(db.String(20), default='Pending', index=True)
    location = db.Column(db.String(200))
    landmark = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    
    # AI Analysis
    ai_confidence = db.Column(db.Float)
    sentiment_score = db.Column(db.Float)
    sentiment_label = db.Column(db.String(20))
    keywords = db.Column(db.Text)  # JSON string
    suggested_category = db.Column(db.String(50))
    suggested_priority = db.Column(db.String(20))
    suggested_department = db.Column(db.String(100))
    
    # Assignment
    assigned_dept = db.Column(db.String(100))
    assigned_dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    assigned_officer = db.Column(db.String(100))
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('officers.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    in_progress_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    
    # Evidence
    evidence_files = db.Column(db.Text)  # JSON array of file paths
    
    # Feedback
    feedback_rating = db.Column(db.Integer)  # 1-5
    feedback_text = db.Column(db.Text)
    feedback_provided_at = db.Column(db.DateTime)
    
    # Metadata
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))
    source = db.Column(db.String(50), default='web')  # web, mobile, email, etc.
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.complaint_id,
            'citizen_name': self.citizen_name,
            'email': self.email,
            'phone': self.phone,
            'complaint_text': self.complaint_text[:200] + '...' if len(self.complaint_text) > 200 else self.complaint_text,
            'full_text': self.complaint_text,
            'category': self.category,
            'priority': self.priority,
            'status': self.status,
            'location': self.location,
            'assigned_dept': self.assigned_dept,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_at_date': self.created_at.strftime('%Y-%m-%d'),
            'created_at_time': self.created_at.strftime('%H:%M:%S'),
            'ai_confidence': round(self.ai_confidence, 2) if self.ai_confidence else None,
            'sentiment': self.sentiment_label,
            'keywords': json.loads(self.keywords) if self.keywords else [],
            'evidence_count': len(json.loads(self.evidence_files)) if self.evidence_files else 0
        }
    
    def get_updates(self):
        """Get all updates for this complaint"""
        return ComplaintUpdate.query.filter_by(complaint_id=self.complaint_id)\
                   .order_by(ComplaintUpdate.created_at.desc()).all()


class ComplaintUpdate(db.Model):
    """Complaint status updates model"""
    __tablename__ = 'complaint_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), db.ForeignKey('complaints.complaint_id'), index=True)
    update_text = db.Column(db.Text)
    status = db.Column(db.String(20))
    updated_by = db.Column(db.String(100))
    updated_by_role = db.Column(db.String(50))
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'update_text': self.update_text,
            'status': self.status,
            'updated_by': self.updated_by,
            'updated_by_role': self.updated_by_role,
            'is_public': self.is_public,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class User(db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='citizen')  # citizen, officer, dept_head, admin
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """Check password"""
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()


class Feedback(db.Model):
    """Citizen feedback model"""
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(20), db.ForeignKey('complaints.complaint_id'))
    rating = db.Column(db.Integer)  # 1-5
    feedback_text = db.Column(db.Text)
    response_time_rating = db.Column(db.Integer)
    resolution_quality_rating = db.Column(db.Integer)
    officer_behavior_rating = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Analytics(db.Model):
    """Analytics data model"""
    __tablename__ = 'analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_complaints = db.Column(db.Integer, default=0)
    pending_complaints = db.Column(db.Integer, default=0)
    resolved_complaints = db.Column(db.Integer, default=0)
    high_priority = db.Column(db.Integer, default=0)
    avg_response_time = db.Column(db.Float, default=0.0)
    avg_resolution_time = db.Column(db.Float, default=0.0)
    category_data = db.Column(db.Text)  # JSON
    department_data = db.Column(db.Text)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# AI COMPLAINT ANALYZER
# ============================================================================

class ComplaintAnalyzer:
    """AI-powered complaint analysis engine"""
    
    def __init__(self):
        # Define category keywords with weights
        self.categories = {
            'Road': {
                'keywords': ['road', 'pothole', 'street', 'asphalt', 'pavement', 'sidewalk', 'footpath', 
                           'speed breaker', 'speed bump', 'traffic signal', 'road damage', 'road repair',
                           'highway', 'lane', 'crossing', 'zebra crossing', 'road marking'],
                'weight': 1.0,
                'subcategories': ['Pothole', 'Road Damage', 'Missing Signage', 'Poor Maintenance', 'Traffic Signal']
            },
            'Water': {
                'keywords': ['water', 'supply', 'leakage', 'pipe', 'tap', 'drinking water', 'borewell', 
                           'tank', 'water tanker', 'water shortage', 'no water', 'water pressure',
                           'water quality', 'contamination', 'dirty water', 'water connection'],
                'weight': 1.0,
                'subcategories': ['No Supply', 'Leakage', 'Poor Quality', 'Low Pressure', 'Connection Issue']
            },
            'Waste': {
                'keywords': ['garbage', 'waste', 'trash', 'rubbish', 'dump', 'litter', 'sanitation', 
                           'bin', 'dustbin', 'waste collection', 'garbage truck', 'sewage', 'drainage',
                           'septic tank', 'manhole', 'sewer', 'cleaning'],
                'weight': 1.0,
                'subcategories': ['Not Collected', 'Bin Overflow', 'Drainage Blocked', 'Stray Animals', 'Odor Issue']
            },
            'Streetlight': {
                'keywords': ['light', 'streetlight', 'lamp', 'bulb', 'pole', 'illumination', 'dark', 
                           'lighting', 'street light', 'lamp post', 'electrical', 'power', 'electricity',
                           'flickering', 'broken light', 'no light'],
                'weight': 1.0,
                'subcategories': ['Not Working', 'Flickering', 'Broken Pole', 'Insufficient Light', 'Timing Issue']
            },
            'Safety': {
                'keywords': ['safety', 'security', 'crime', 'threat', 'dangerous', 'suspicious', 'police', 
                           'patrol', 'harassment', 'theft', 'robbery', 'break-in', 'vandalism',
                           'stranger', 'loitering', 'unsafe', 'cctv', 'camera'],
                'weight': 1.2,  # Higher weight for safety issues
                'subcategories': ['Suspicious Activity', 'Harassment', 'Poor Lighting', 'No Patrol', 'CCTV Required']
            },
            'Drainage': {
                'keywords': ['drain', 'blockage', 'flood', 'water logging', 'sewage', 'overflow', 
                           'drainage', 'storm drain', 'rain water', 'stagnant water', 'mosquito',
                           'bad smell', 'foul smell', 'choked drain'],
                'weight': 1.0,
                'subcategories': ['Blocked Drain', 'Water Logging', 'Overflow', 'Bad Odor', 'Mosquito Breeding']
            },
            'Park': {
                'keywords': ['park', 'garden', 'playground', 'bench', 'fountain', 'children park',
                           'green space', 'public garden', 'swing', 'slide', 'park maintenance'],
                'weight': 0.8,
                'subcategories': ['Maintenance', 'Equipment Broken', 'Cleanliness', 'Security', 'Lighting']
            },
            'Noise': {
                'keywords': ['noise', 'sound', 'loud', 'disturbance', 'construction noise', 'music',
                           'party noise', 'horn', 'traffic noise', 'industrial noise', 'silence'],
                'weight': 0.9,
                'subcategories': ['Construction', 'Loud Music', 'Vehicle Horn', 'Industrial', 'Animal']
            },
            'Electricity': {
                'keywords': ['electricity', 'power', 'voltage', 'wire', 'cable', 'transformer',
                           'power cut', 'power outage', 'tripping', 'sparking', 'shock',
                           'meter', 'bill', 'connection'],
                'weight': 1.1,
                'subcategories': ['Power Cut', 'Voltage Fluctuation', 'Wire Snapping', 'Meter Issue', 'Billing']
            },
            'Public Transport': {
                'keywords': ['bus', 'transport', 'vehicle', 'public transport', 'bus stop', 'auto',
                           'taxi', 'metro', 'train', 'ticket', 'conductor', 'driver'],
                'weight': 0.8,
                'subcategories': ['Bus Delay', 'Driver Behavior', 'Overcrowding', 'Stop Issue', 'Route Issue']
            }
        }
        
        # Priority keywords with weights
        self.priority_keywords = {
            'High': {
                'keywords': ['emergency', 'urgent', 'accident', 'fire', 'collapse', 'injury', 
                           'death', 'critical', 'dangerous', 'life threatening', 'immediate',
                           'explosion', 'gas leak', 'chemical', 'hazard', 'crisis', 'disaster'],
                'weight': 2.0
            },
            'Medium': {
                'keywords': ['leakage', 'broken', 'blocked', 'damage', 'failure', 'stuck', 
                           'overflow', 'not working', 'issue', 'problem', 'complaint',
                           'repair', 'fix', 'replace', 'maintenance'],
                'weight': 1.0
            },
            'Low': {
                'keywords': ['suggestion', 'request', 'inquiry', 'information', 'question',
                           'when', 'how', 'why', 'status', 'update', 'follow up'],
                'weight': 0.5
            }
        }
        
        # Sentiment analysis keywords
        self.sentiment_keywords = {
            'Very Negative': ['terrible', 'horrible', 'worst', 'useless', 'furious', 'angry', 
                             'disgusting', 'shameful', 'negligence', 'incompetent'],
            'Negative': ['bad', 'poor', 'dissatisfied', 'frustrated', 'annoyed', 'disappointed',
                        'unhappy', 'unsatisfactory', 'slow', 'waste'],
            'Neutral': ['ok', 'okay', 'fine', 'average', 'moderate', 'normal', 'regular',
                       'standard', 'usual'],
            'Positive': ['good', 'nice', 'satisfied', 'happy', 'pleased', 'appreciate',
                        'thankful', 'grateful', 'helpful', 'prompt'],
            'Very Positive': ['excellent', 'outstanding', 'wonderful', 'amazing', 'perfect',
                             'exceptional', 'remarkable', 'fantastic']
        }
        
        # Department mapping
        self.department_mapping = {
            'Road': 'Public Works Department',
            'Water': 'Water Supply Department',
            'Waste': 'Sanitation Department',
            'Streetlight': 'Electricity Department',
            'Safety': 'Police Department',
            'Drainage': 'Public Works Department',
            'Park': 'Parks and Recreation Department',
            'Noise': 'Environmental Protection Department',
            'Electricity': 'Electricity Board',
            'Public Transport': 'Transport Department'
        }
    
    def analyze_category(self, text):
        """Predict complaint category with confidence score"""
        text_lower = text.lower()
        scores = {}
        
        for category, data in self.categories.items():
            score = 0
            matched_keywords = []
            
            for keyword in data['keywords']:
                if keyword in text_lower:
                    score += data['weight']
                    matched_keywords.append(keyword)
            
            scores[category] = {
                'score': score,
                'matched_keywords': matched_keywords
            }
        
        # Get category with highest score
        if max(s['score'] for s in scores.values()) > 0:
            predicted = max(scores, key=lambda x: scores[x]['score'])
            # Calculate confidence percentage
            max_possible_score = sum(data['weight'] for data in self.categories.values())
            confidence = (scores[predicted]['score'] / max_possible_score) * 100
            confidence = min(confidence * 2, 100)  # Scale up a bit
        else:
            predicted = 'Other'
            confidence = 50
        
        # Determine subcategory
        subcategory = self._determine_subcategory(text_lower, predicted)
        
        return predicted, subcategory, round(confidence, 2), scores[predicted]['matched_keywords']
    
    def _determine_subcategory(self, text, category):
        """Determine subcategory within a category"""
        if category in self.categories:
            subcategories = self.categories[category]['subcategories']
            # Simple matching - in production, use more sophisticated method
            for subcat in subcategories:
                if subcat.lower() in text:
                    return subcat
            return subcategories[0] if subcategories else 'General'
        return 'General'
    
    def determine_priority(self, text):
        """Determine complaint priority with reasoning"""
        text_lower = text.lower()
        scores = {}
        
        for priority, data in self.priority_keywords.items():
            score = 0
            matched_keywords = []
            
            for keyword in data['keywords']:
                if keyword in text_lower:
                    score += data['weight']
                    matched_keywords.append(keyword)
            
            scores[priority] = {
                'score': score,
                'matched_keywords': matched_keywords
            }
        
        # Determine priority based on highest score
        if scores['High']['score'] > 0:
            priority = 'High'
        elif scores['Medium']['score'] > 0:
            priority = 'Medium'
        else:
            priority = 'Low'
        
        # Get reasoning
        reasoning = scores[priority]['matched_keywords'][:3] if scores[priority]['matched_keywords'] else []
        
        return priority, reasoning
    
    def analyze_sentiment(self, text):
        """Analyze sentiment of complaint"""
        text_lower = text.lower()
        scores = {}
        
        for sentiment, keywords in self.sentiment_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            scores[sentiment] = score
        
        # Get sentiment with highest score
        if max(scores.values()) > 0:
            sentiment = max(scores, key=scores.get)
            score = scores[sentiment] / len(self.sentiment_keywords[sentiment])
        else:
            sentiment = 'Neutral'
            score = 0.5
        
        return sentiment, round(score, 2)
    
    def extract_keywords(self, text):
        """Extract important keywords from complaint"""
        # Clean text
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'were', 'are', 'be',
                     'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them'}
        
        # Count word frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:10]]
        
        return keywords
    
    def suggest_department(self, category):
        """Suggest department based on category"""
        return self.department_mapping.get(category, 'General Administration')
    
    def analyze_complaint(self, text):
        """Complete analysis of complaint"""
        category, subcategory, confidence, matched_keywords = self.analyze_category(text)
        priority, priority_reason = self.determine_priority(text)
        sentiment, sentiment_score = self.analyze_sentiment(text)
        keywords = self.extract_keywords(text)
        department = self.suggest_department(category)
        
        return {
            'category': category,
            'subcategory': subcategory,
            'confidence': confidence,
            'matched_keywords': matched_keywords,
            'priority': priority,
            'priority_reason': priority_reason,
            'sentiment': sentiment,
            'sentiment_score': sentiment_score,
            'keywords': keywords,
            'department': department
        }


# Initialize analyzer
analyzer = ComplaintAnalyzer()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_complaint_id():
    """Generate unique complaint ID"""
    date_part = datetime.now().strftime('%y%m%d')
    
    # Get count of complaints today to create sequence
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count_today = Complaint.query.filter(Complaint.created_at >= today_start).count()
    
    sequence = str(count_today + 1).zfill(4)
    random_part = secrets.randbelow(1000)
    
    return f"CMP{date_part}{sequence}{random_part}"


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_file_type(filename):
    """Determine file type for storage"""
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['png', 'jpg', 'jpeg', 'gif']:
        return 'images'
    elif ext in ['mp4', 'mov', 'avi']:
        return 'videos'
    else:
        return 'documents'


def save_uploaded_file(file, complaint_id):
    """Save uploaded file and return path"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_type = get_file_type(filename)
        
        # Create unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{complaint_id}_{timestamp}_{filename}"
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_type, unique_filename)
        file.save(file_path)
        
        # Return relative path for database
        return f"/static/uploads/{file_type}/{unique_filename}"
    
    return None


def validate_email(email):
    """Validate email format"""
    if not email:
        return False
    parsed = parseaddr(email)
    return '@' in parsed[1] and '.' in parsed[1].split('@')[1]


def validate_phone(phone):
    """Validate phone number (simple validation)"""
    if not phone:
        return True  # Phone is optional
    # Remove common separators
    phone = re.sub(r'[\s\-\(\)\+]', '', phone)
    return phone.isdigit() and len(phone) >= 10


def get_client_ip():
    """Get client IP address from request"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr


def calculate_response_time(complaint):
    """Calculate response time in hours"""
    if complaint.assigned_at and complaint.created_at:
        delta = complaint.assigned_at - complaint.created_at
        return delta.total_seconds() / 3600
    return None


def calculate_resolution_time(complaint):
    """Calculate resolution time in hours"""
    if complaint.resolved_at and complaint.created_at:
        delta = complaint.resolved_at - complaint.created_at
        return delta.total_seconds() / 3600
    return None


def update_department_stats(dept_id):
    """Update department statistics"""
    dept = Department.query.get(dept_id)
    if dept:
        complaints = Complaint.query.filter_by(assigned_dept_id=dept_id).all()
        
        total = len(complaints)
        resolved = sum(1 for c in complaints if c.status == 'Resolved')
        pending = sum(1 for c in complaints if c.status == 'Pending')
        
        # Calculate average response time
        response_times = [calculate_response_time(c) for c in complaints if c.assigned_at]
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        # Calculate average resolution time
        resolution_times = [calculate_resolution_time(c) for c in complaints if c.resolved_at]
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        # Calculate satisfaction rate
        feedbacks = Feedback.query.filter(Feedback.complaint_id.in_([c.complaint_id for c in complaints])).all()
        avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks) if feedbacks else 0
        
        dept.total_complaints = total
        dept.resolved_complaints = resolved
        dept.pending_complaints = pending
        dept.avg_response_time = round(avg_response, 2)
        dept.avg_resolution_time = round(avg_resolution, 2)
        dept.satisfaction_rate = round(avg_rating * 20, 2)  # Convert 1-5 to percentage
        
        db.session.commit()


# ============================================================================
# ROUTES FOR PAGES
# ============================================================================

@app.route('/')
def home():
    """Home page with complaint form"""
    # Get statistics for display
    total = Complaint.query.count()
    pending = Complaint.query.filter_by(status='Pending').count()
    in_progress = Complaint.query.filter_by(status='In Progress').count()
    resolved = Complaint.query.filter_by(status='Resolved').count()
    high_priority = Complaint.query.filter_by(priority='High').count()
    
    # Get today's count
    today = datetime.now().date()
    today_count = Complaint.query.filter(db.func.date(Complaint.created_at) == today).count()
    
    # Get category counts
    categories = {}
    for category in analyzer.categories.keys():
        count = Complaint.query.filter_by(category=category).count()
        categories[category] = count
    
    # Get recent complaints
    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all()
    
    return render_template('home.html',
                         total=total,
                         pending=pending,
                         in_progress=in_progress,
                         resolved=resolved,
                         high_priority=high_priority,
                         today_count=today_count,
                         categories=categories,
                         recent_complaints=[c.to_dict() for c in recent_complaints])


@app.route('/file-complaint')
def file_complaint():
    """File complaint page"""
    return render_template('file-complaint.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard page with analytics"""
    return render_template('dashboard.html')


@app.route('/track')
def track():
    """Track complaints page"""
    return render_template('track.html')


@app.route('/complaint/<complaint_id>')
def complaint_details(complaint_id):
    """Complaint details page"""
    complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
    if not complaint:
        flash('Complaint not found', 'error')
        return redirect(url_for('track'))
    
    updates = complaint.get_updates()
    return render_template('complaint_details.html', 
                         complaint=complaint.to_dict(),
                         updates=[u.to_dict() for u in updates])


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/analyze-complaint', methods=['POST'])
def api_analyze_complaint():
    """API endpoint to analyze complaint text"""
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text or len(text) < 10:
            return jsonify({
                'success': False,
                'error': 'Please provide sufficient text for analysis'
            }), 400
        
        # Analyze complaint
        analysis = analyzer.analyze_complaint(text)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/submit-complaint', methods=['POST'])
def api_submit_complaint():
    """API endpoint to submit new complaint"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'complaint_text', 'location']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field.replace("_", " ").title()} is required'
                }), 400
        
        # Validate email
        if not validate_email(data['email']):
            return jsonify({'success': False, 'error': 'Invalid email format'}), 400
        
        # Validate phone if provided
        if data.get('phone') and not validate_phone(data['phone']):
            return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
        
        # Analyze complaint with AI
        analysis = analyzer.analyze_complaint(data['complaint_text'])
        
        # Generate complaint ID
        complaint_id = generate_complaint_id()
        
        # Get or create department
        dept_name = analysis['department']
        dept = Department.query.filter_by(name=dept_name).first()
        if not dept:
            dept = Department(name=dept_name)
            db.session.add(dept)
            db.session.flush()
        
        # Create new complaint
        complaint = Complaint(
            complaint_id=complaint_id,
            citizen_name=data['name'],
            email=data['email'],
            phone=data.get('phone', ''),
            alternate_phone=data.get('alternate_phone', ''),
            address=data.get('address', ''),
            complaint_text=data['complaint_text'],
            location=data['location'],
            landmark=data.get('landmark', ''),
            
            # AI Analysis results
            category=analysis['category'],
            subcategory=analysis['subcategory'],
            priority=analysis['priority'],
            ai_confidence=analysis['confidence'],
            sentiment_score=analysis['sentiment_score'],
            sentiment_label=analysis['sentiment'],
            keywords=json.dumps(analysis['keywords']),
            suggested_category=analysis['category'],
            suggested_priority=analysis['priority'],
            suggested_department=analysis['department'],
            
            # Assignment
            assigned_dept=analysis['department'],
            assigned_dept_id=dept.id,
            
            # Metadata
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            source='web'
        )
        
        db.session.add(complaint)
        
        # Update department stats
        dept.total_complaints += 1
        dept.pending_complaints += 1
        
        db.session.commit()
        
        # Create initial update
        update = ComplaintUpdate(
            complaint_id=complaint_id,
            update_text='Complaint submitted successfully and analyzed by AI',
            status='Pending',
            updated_by='AI System',
            updated_by_role='system'
        )
        db.session.add(update)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'complaint_id': complaint_id,
            'analysis': {
                'category': analysis['category'],
                'priority': analysis['priority'],
                'department': analysis['department'],
                'confidence': analysis['confidence'],
                'sentiment': analysis['sentiment'],
                'keywords': analysis['keywords']
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/upload-evidence', methods=['POST'])
def api_upload_evidence():
    """API endpoint to upload evidence files"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        complaint_id = request.form.get('complaint_id')
        
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'}), 400
        
        # Save file
        file_path = save_uploaded_file(file, complaint_id or 'temp')
        
        if not file_path:
            return jsonify({'success': False, 'error': 'Failed to save file'}), 500
        
        # Update complaint if complaint_id provided
        if complaint_id and complaint_id != 'temp':
            complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
            if complaint:
                existing_files = json.loads(complaint.evidence_files) if complaint.evidence_files else []
                if len(existing_files) >= app.config['MAX_FILES_PER_COMPLAINT']:
                    return jsonify({
                        'success': False, 
                        'error': f'Maximum {app.config["MAX_FILES_PER_COMPLAINT"]} files allowed'
                    }), 400
                
                existing_files.append(file_path)
                complaint.evidence_files = json.dumps(existing_files)
                db.session.commit()
        
        return jsonify({
            'success': True,
            'file_path': file_path,
            'message': 'File uploaded successfully'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard-stats', methods=['GET'])
def api_dashboard_stats():
    """API endpoint to get dashboard statistics"""
    try:
        # Get time period from query params
        period = request.args.get('period', 'week')
        
        # Date ranges
        today = datetime.utcnow().date()
        if period == 'week':
            start_date = today - timedelta(days=7)
            group_by = 'day'
        elif period == 'month':
            start_date = today - timedelta(days=30)
            group_by = 'day'
        elif period == 'year':
            start_date = today - timedelta(days=365)
            group_by = 'month'
        else:
            start_date = today - timedelta(days=7)
            group_by = 'day'
        
        # Basic stats
        total = Complaint.query.count()
        pending = Complaint.query.filter_by(status='Pending').count()
        in_progress = Complaint.query.filter_by(status='In Progress').count()
        resolved = Complaint.query.filter_by(status='Resolved').count()
        
        # Priority distribution
        high_priority = Complaint.query.filter_by(priority='High').count()
        medium_priority = Complaint.query.filter_by(priority='Medium').count()
        low_priority = Complaint.query.filter_by(priority='Low').count()
        
        # Category distribution
        categories = {}
        for category in analyzer.categories.keys():
            count = Complaint.query.filter_by(category=category).count()
            if count > 0:
                categories[category] = count
        
        # Add 'Other' category
        other_count = Complaint.query.filter(
            ~Complaint.category.in_(list(analyzer.categories.keys()))
        ).count()
        if other_count > 0:
            categories['Other'] = other_count
        
        # Trend data
        trend_labels = []
        trend_data = []
        
        if group_by == 'day':
            for i in range(7):
                date = today - timedelta(days=6-i)
                trend_labels.append(date.strftime('%a'))
                
                count = Complaint.query.filter(
                    db.func.date(Complaint.created_at) == date
                ).count()
                trend_data.append(count)
        else:  # month
            for i in range(12):
                month = today - timedelta(days=30*i)
                month_start = datetime(month.year, month.month, 1).date()
                if month.month == 12:
                    month_end = datetime(month.year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    month_end = datetime(month.year, month.month + 1, 1).date() - timedelta(days=1)
                
                count = Complaint.query.filter(
                    Complaint.created_at >= month_start,
                    Complaint.created_at <= month_end
                ).count()
                
                trend_labels.append(month.strftime('%b'))
                trend_data.append(count)
            
            trend_labels.reverse()
            trend_data.reverse()
        
        # Department performance
        departments = Department.query.order_by(Department.total_complaints.desc()).limit(5).all()
        dept_names = []
        dept_resolved = []
        dept_pending = []
        
        for dept in departments:
            dept_names.append(dept.name[:15] + '...' if len(dept.name) > 15 else dept.name)
            dept_resolved.append(dept.resolved_complaints)
            dept_pending.append(dept.pending_complaints)
        
        # Response time stats
        resolved_complaints = Complaint.query.filter(Complaint.resolved_at.isnot(None)).all()
        response_times = []
        for c in resolved_complaints:
            time = calculate_resolution_time(c)
            if time:
                response_times.append(time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'pending': pending,
                'in_progress': in_progress,
                'resolved': resolved,
                'avg_response_time': round(avg_response_time, 1)
            },
            'priority_distribution': {
                'High': high_priority,
                'Medium': medium_priority,
                'Low': low_priority
            },
            'category_distribution': categories,
            'trend': {
                'labels': trend_labels,
                'data': trend_data
            },
            'department_performance': {
                'names': dept_names,
                'resolved': dept_resolved,
                'pending': dept_pending
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/complaints', methods=['GET'])
def api_get_complaints():
    """API endpoint to get complaints list with filters"""
    try:
        # Get filter parameters
        status = request.args.get('status', 'all')
        priority = request.args.get('priority', 'all')
        category = request.args.get('category', 'all')
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # Build query
        query = Complaint.query
        
        if status and status != 'all':
            query = query.filter_by(status=status.capitalize())
        
        if priority and priority != 'all':
            query = query.filter_by(priority=priority.capitalize())
        
        if category and category != 'all':
            query = query.filter_by(category=category.capitalize())
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Complaint.complaint_id.ilike(search_term),
                    Complaint.citizen_name.ilike(search_term),
                    Complaint.email.ilike(search_term),
                    Complaint.complaint_text.ilike(search_term),
                    Complaint.location.ilike(search_term)
                )
            )
        
        # Order by priority and date
        query = query.order_by(
            db.case(
                (Complaint.priority == 'High', 1),
                (Complaint.priority == 'Medium', 2),
                (Complaint.priority == 'Low', 3),
                else_=4
            ),
            Complaint.created_at.desc()
        )
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        complaints = []
        for complaint in paginated.items:
            complaints.append(complaint.to_dict())
        
        return jsonify({
            'success': True,
            'complaints': complaints,
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/complaint/<complaint_id>', methods=['GET'])
def api_get_complaint_details(complaint_id):
    """API endpoint to get detailed complaint information"""
    try:
        complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
        
        if not complaint:
            return jsonify({'success': False, 'error': 'Complaint not found'}), 404
        
        # Get updates
        updates = ComplaintUpdate.query.filter_by(complaint_id=complaint_id)\
                     .order_by(ComplaintUpdate.created_at.desc()).all()
        
        # Get feedback if any
        feedback = Feedback.query.filter_by(complaint_id=complaint_id).first()
        
        # Get department info
        department = Department.query.get(complaint.assigned_dept_id)
        
        # Parse keywords and evidence
        keywords = json.loads(complaint.keywords) if complaint.keywords else []
        evidence_files = json.loads(complaint.evidence_files) if complaint.evidence_files else []
        
        return jsonify({
            'success': True,
            'complaint': {
                'id': complaint.complaint_id,
                'citizen_name': complaint.citizen_name,
                'email': complaint.email,
                'phone': complaint.phone,
                'alternate_phone': complaint.alternate_phone,
                'address': complaint.address,
                'complaint_text': complaint.complaint_text,
                'category': complaint.category,
                'subcategory': complaint.subcategory,
                'priority': complaint.priority,
                'status': complaint.status,
                'location': complaint.location,
                'landmark': complaint.landmark,
                'assigned_dept': complaint.assigned_dept,
                'department_info': department.to_dict() if department else None,
                'created_at': complaint.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': complaint.updated_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.updated_at else None,
                'assigned_at': complaint.assigned_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.assigned_at else None,
                'resolved_at': complaint.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if complaint.resolved_at else None,
                
                # AI Analysis
                'ai_confidence': complaint.ai_confidence,
                'sentiment': complaint.sentiment_label,
                'sentiment_score': complaint.sentiment_score,
                'keywords': keywords,
                'evidence_files': evidence_files,
                
                # Feedback
                'feedback': {
                    'rating': feedback.rating if feedback else None,
                    'text': feedback.feedback_text if feedback else None
                } if feedback else None,
                
                # Updates
                'updates': [u.to_dict() for u in updates]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/complaint/<complaint_id>/update', methods=['POST'])
def api_update_complaint_status(complaint_id):
    """API endpoint to update complaint status"""
    try:
        data = request.json
        complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
        
        if not complaint:
            return jsonify({'success': False, 'error': 'Complaint not found'}), 404
        
        old_status = complaint.status
        new_status = data.get('status', old_status)
        update_text = data.get('update_text', '')
        updated_by = data.get('updated_by', 'System')
        updated_by_role = data.get('updated_by_role', 'system')
        
        # Update status and timestamps
        if new_status != old_status:
            complaint.status = new_status
            complaint.updated_at = datetime.utcnow()
            
            if new_status == 'In Progress' and not complaint.in_progress_at:
                complaint.in_progress_at = datetime.utcnow()
            
            if new_status == 'Assigned' and not complaint.assigned_at:
                complaint.assigned_at = datetime.utcnow()
            
            if new_status == 'Resolved' and not complaint.resolved_at:
                complaint.resolved_at = datetime.utcnow()
                
                # Update department resolved count
                if complaint.assigned_dept_id:
                    dept = Department.query.get(complaint.assigned_dept_id)
                    if dept:
                        dept.resolved_complaints += 1
                        dept.pending_complaints -= 1
            
            if new_status == 'Closed':
                complaint.closed_at = datetime.utcnow()
        
        # Create update record
        update = ComplaintUpdate(
            complaint_id=complaint_id,
            update_text=update_text or f'Status changed from {old_status} to {new_status}',
            status=new_status,
            updated_by=updated_by,
            updated_by_role=updated_by_role
        )
        
        db.session.add(update)
        db.session.commit()
        
        # Update department stats
        if complaint.assigned_dept_id:
            update_department_stats(complaint.assigned_dept_id)
        
        return jsonify({
            'success': True,
            'message': 'Complaint updated successfully',
            'update': update.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/complaint/<complaint_id>/feedback', methods=['POST'])
def api_submit_feedback(complaint_id):
    """API endpoint to submit feedback for complaint"""
    try:
        data = request.json
        complaint = Complaint.query.filter_by(complaint_id=complaint_id).first()
        
        if not complaint:
            return jsonify({'success': False, 'error': 'Complaint not found'}), 404
        
        # Validate rating
        rating = data.get('rating')
        if not rating or rating < 1 or rating > 5:
            return jsonify({'success': False, 'error': 'Rating must be between 1 and 5'}), 400
        
        # Create feedback
        feedback = Feedback(
            complaint_id=complaint_id,
            rating=rating,
            feedback_text=data.get('feedback_text', ''),
            response_time_rating=data.get('response_time_rating'),
            resolution_quality_rating=data.get('resolution_quality_rating'),
            officer_behavior_rating=data.get('officer_behavior_rating')
        )
        
        db.session.add(feedback)
        
        # Update complaint with feedback
        complaint.feedback_rating = rating
        complaint.feedback_text = data.get('feedback_text', '')
        complaint.feedback_provided_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update department satisfaction rate
        if complaint.assigned_dept_id:
            update_department_stats(complaint.assigned_dept_id)
        
        return jsonify({
            'success': True,
            'message': 'Feedback submitted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/search', methods=['GET'])
def api_search():
    """API endpoint to search complaints"""
    try:
        query = request.args.get('q', '')
        
        if len(query) < 3:
            return jsonify({
                'success': False,
                'error': 'Search query must be at least 3 characters'
            }), 400
        
        search_term = f"%{query}%"
        
        # Search in multiple fields
        results = Complaint.query.filter(
            db.or_(
                Complaint.complaint_id.ilike(search_term),
                Complaint.citizen_name.ilike(search_term),
                Complaint.email.ilike(search_term),
                Complaint.phone.ilike(search_term),
                Complaint.complaint_text.ilike(search_term),
                Complaint.location.ilike(search_term),
                Complaint.category.ilike(search_term)
            )
        ).order_by(
            Complaint.priority.desc(),
            Complaint.created_at.desc()
        ).limit(20).all()
        
        return jsonify({
            'success': True,
            'results': [r.to_dict() for r in results],
            'count': len(results)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/categories', methods=['GET'])
def api_get_categories():
    """API endpoint to get all categories with subcategories"""
    try:
        categories = []
        for cat, data in analyzer.categories.items():
            categories.append({
                'name': cat,
                'subcategories': data['subcategories'],
                'count': Complaint.query.filter_by(category=cat).count()
            })
        
        return jsonify({
            'success': True,
            'categories': categories
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/departments', methods=['GET'])
def api_get_departments():
    """API endpoint to get all departments"""
    try:
        departments = Department.query.order_by(Department.name).all()
        
        return jsonify({
            'success': True,
            'departments': [d.to_dict() for d in departments]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats/trends', methods=['GET'])
def api_trend_analytics():
    """API endpoint to get trend analytics"""
    try:
        period = request.args.get('period', 'month')
        
        today = datetime.utcnow().date()
        
        if period == 'week':
            days = 7
            interval = 'day'
        elif period == 'month':
            days = 30
            interval = 'day'
        elif period == 'quarter':
            days = 90
            interval = 'week'
        elif period == 'year':
            days = 365
            interval = 'month'
        else:
            days = 30
            interval = 'day'
        
        labels = []
        data = []
        
        if interval == 'day':
            for i in range(days-1, -1, -1):
                date = today - timedelta(days=i)
                count = Complaint.query.filter(
                    db.func.date(Complaint.created_at) == date
                ).count()
                
                labels.append(date.strftime('%d %b'))
                data.append(count)
        
        elif interval == 'week':
            for i in range(0, days, 7):
                week_start = today - timedelta(days=days-i-7)
                week_end = week_start + timedelta(days=6)
                
                count = Complaint.query.filter(
                    Complaint.created_at >= week_start,
                    Complaint.created_at <= week_end + timedelta(days=1)
                ).count()
                
                labels.append(f"{week_start.strftime('%d %b')}")
                data.append(count)
        
        else:  # month
            for i in range(11, -1, -1):
                month = today - timedelta(days=30*i)
                month_start = datetime(month.year, month.month, 1).date()
                if month.month == 12:
                    month_end = datetime(month.year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    month_end = datetime(month.year, month.month + 1, 1).date() - timedelta(days=1)
                
                count = Complaint.query.filter(
                    Complaint.created_at >= month_start,
                    Complaint.created_at <= month_end
                ).count()
                
                labels.append(month.strftime('%b %Y'))
                data.append(count)
        
        return jsonify({
            'success': True,
            'labels': labels,
            'data': data,
            'period': period,
            'interval': interval
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin')
def admin_panel():
    """Admin panel page"""
    return render_template('admin.html')


@app.route('/api/admin/departments', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_departments():
    """API endpoint for department management"""
    try:
        if request.method == 'GET':
            departments = Department.query.all()
            return jsonify({
                'success': True,
                'departments': [d.to_dict() for d in departments]
            })
        
        elif request.method == 'POST':
            data = request.json
            dept = Department(
                name=data['name'],
                head=data.get('head'),
                email=data.get('email'),
                phone=data.get('phone'),
                description=data.get('description')
            )
            db.session.add(dept)
            db.session.commit()
            return jsonify({'success': True, 'department': dept.to_dict()})
        
        elif request.method == 'PUT':
            data = request.json
            dept = Department.query.get(data['id'])
            if not dept:
                return jsonify({'success': False, 'error': 'Department not found'}), 404
            
            dept.name = data.get('name', dept.name)
            dept.head = data.get('head', dept.head)
            dept.email = data.get('email', dept.email)
            dept.phone = data.get('phone', dept.phone)
            dept.description = data.get('description', dept.description)
            
            db.session.commit()
            return jsonify({'success': True, 'department': dept.to_dict()})
        
        elif request.method == 'DELETE':
            dept_id = request.args.get('id')
            dept = Department.query.get(dept_id)
            if not dept:
                return jsonify({'success': False, 'error': 'Department not found'}), 404
            
            db.session.delete(dept)
            db.session.commit()
            return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/stats', methods=['GET'])
def api_admin_stats():
    """API endpoint for admin statistics"""
    try:
        # Overall stats
        total_complaints = Complaint.query.count()
        total_departments = Department.query.count()
        total_officers = Officer.query.count()
        total_users = User.query.count()
        
        # Complaints by status
        status_counts = {
            'pending': Complaint.query.filter_by(status='Pending').count(),
            'in_progress': Complaint.query.filter_by(status='In Progress').count(),
            'resolved': Complaint.query.filter_by(status='Resolved').count(),
            'closed': Complaint.query.filter_by(status='Closed').count()
        }
        
        # Monthly trends
        current_year = datetime.now().year
        monthly_data = []
        
        for month in range(1, 13):
            start_date = datetime(current_year, month, 1)
            if month == 12:
                end_date = datetime(current_year + 1, 1, 1)
            else:
                end_date = datetime(current_year, month + 1, 1)
            
            count = Complaint.query.filter(
                Complaint.created_at >= start_date,
                Complaint.created_at < end_date
            ).count()
            
            monthly_data.append({
                'month': start_date.strftime('%b'),
                'count': count
            })
        
        # Department performance
        dept_performance = []
        depts = Department.query.all()
        for dept in depts:
            resolution_rate = (dept.resolved_complaints / dept.total_complaints * 100) if dept.total_complaints > 0 else 0
            dept_performance.append({
                'name': dept.name,
                'total': dept.total_complaints,
                'resolved': dept.resolved_complaints,
                'resolution_rate': round(resolution_rate, 1),
                'avg_response': dept.avg_response_time
            })
        
        return jsonify({
            'success': True,
            'overall': {
                'total_complaints': total_complaints,
                'total_departments': total_departments,
                'total_officers': total_officers,
                'total_users': total_users
            },
            'status_counts': status_counts,
            'monthly_trends': monthly_data,
            'department_performance': dept_performance
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return render_template('500.html'), 500


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

@app.before_first_request
def initialize_database():
    """Initialize database with default data"""
    db.create_all()
    
    # Create default departments if they don't exist
    default_departments = [
        {
            'name': 'Public Works Department',
            'head': 'Chief Engineer',
            'email': 'pwd@example.gov',
            'phone': '+1-800-555-0101',
            'description': 'Handles roads, bridges, and public infrastructure'
        },
        {
            'name': 'Water Supply Department',
            'head': 'Water Commissioner',
            'email': 'water@example.gov',
            'phone': '+1-800-555-0102',
            'description': 'Manages water supply, pipelines, and water quality'
        },
        {
            'name': 'Sanitation Department',
            'head': 'Sanitation Officer',
            'email': 'sanitation@example.gov',
            'phone': '+1-800-555-0103',
            'description': 'Handles waste management, garbage collection, and cleaning'
        },
        {
            'name': 'Electricity Department',
            'head': 'Chief Electrical Engineer',
            'email': 'electricity@example.gov',
            'phone': '+1-800-555-0104',
            'description': 'Manages streetlights, power supply, and electrical infrastructure'
        },
        {
            'name': 'Police Department',
            'head': 'Police Commissioner',
            'email': 'police@example.gov',
            'phone': '+1-800-555-0105',
            'description': 'Handles public safety, crime prevention, and security'
        },
        {
            'name': 'Parks and Recreation Department',
            'head': 'Park Director',
            'email': 'parks@example.gov',
            'phone': '+1-800-555-0106',
            'description': 'Maintains parks, gardens, and public spaces'
        },
        {
            'name': 'Environmental Protection Department',
            'head': 'Environmental Officer',
            'email': 'environment@example.gov',
            'phone': '+1-800-555-0107',
            'description': 'Handles noise pollution, environmental issues'
        },
        {
            'name': 'Transport Department',
            'head': 'Transport Commissioner',
            'email': 'transport@example.gov',
            'phone': '+1-800-555-0108',
            'description': 'Manages public transport, buses, and traffic'
        },
        {
            'name': 'General Administration',
            'head': 'Administrative Officer',
            'email': 'admin@example.gov',
            'phone': '+1-800-555-0199',
            'description': 'Handles miscellaneous complaints and general inquiries'
        }
    ]
    
    for dept_data in default_departments:
        dept = Department.query.filter_by(name=dept_data['name']).first()
        if not dept:
            dept = Department(**dept_data)
            db.session.add(dept)
    
    # Create admin user if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.gov',
            full_name='System Administrator',
            role='admin'
        )
        admin.set_password('Admin@123')  # Change in production!
        db.session.add(admin)
    
    db.session.commit()
    
    print("Database initialized successfully!")


# ============================================================================
# TEMPLATE CONTEXT PROCESSORS
# ============================================================================

@app.context_processor
def utility_processor():
    """Add utility functions to template context"""
    def now():
        return datetime.now()
    
    def format_date(date, format='%Y-%m-%d'):
        if date:
            return date.strftime(format)
        return ''
    
    def get_status_badge_class(status):
        badges = {
            'Pending': 'warning',
            'In Progress': 'info',
            'Resolved': 'success',
            'Closed': 'secondary',
            'Rejected': 'danger'
        }
        return badges.get(status, 'light')
    
    def get_priority_badge_class(priority):
        badges = {
            'High': 'danger',
            'Medium': 'warning',
            'Low': 'success'
        }
        return badges.get(priority, 'light')
    
    return dict(
        now=now,
        format_date=format_date,
        get_status_badge_class=get_status_badge_class,
        get_priority_badge_class=get_priority_badge_class
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)