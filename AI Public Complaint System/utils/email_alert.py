import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_alert(complaint):
    """Send email alert for high priority complaints"""
    
    # Email configuration
    sender_email = "your-email@gmail.com"
    sender_password = "your-app-password"
    
    # Department emails mapping
    dept_emails = {
        'Public Works Department': 'pwd@example.com',
        'Water Supply Department': 'water@example.com',
        'Sanitation Department': 'sanitation@example.com',
        'Electricity Department': 'electricity@example.com',
        'Police Department': 'police@example.com'
    }
    
    # Get department email
    dept_email = dept_emails.get(complaint.assigned_dept)
    
    if dept_email:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = dept_email
        msg['Subject'] = f"URGENT: High Priority Complaint #{complaint.id}"
        
        # Email body
        body = f"""
        <h2>High Priority Complaint Alert</h2>
        
        <p><strong>Complaint ID:</strong> {complaint.id}</p>
        <p><strong>Citizen:</strong> {complaint.citizen_name}</p>
        <p><strong>Contact:</strong> {complaint.email} | {complaint.phone}</p>
        <p><strong>Location:</strong> {complaint.location}</p>
        <p><strong>Category:</strong> {complaint.category}</p>
        <p><strong>Complaint:</strong></p>
        <p>{complaint.complaint_text}</p>
        <p><strong>AI Confidence:</strong> {complaint.ai_confidence*100:.2f}%</p>
        
        <p>Please take immediate action on this complaint.</p>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        try:
            # Send email
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            print(f"Alert sent to {dept_email}")
        except Exception as e:
            print(f"Failed to send alert: {e}")

def send_status_update(complaint, citizen_email):
    """Send status update to citizen"""
    
    msg = MIMEMultipart()
    msg['From'] = "noreply@complaint.gov"
    msg['To'] = citizen_email
    msg['Subject'] = f"Complaint #{complaint.id} Status Update"
    
    body = f"""
    <h3>Your Complaint Status</h3>
    
    <p><strong>Complaint ID:</strong> {complaint.id}</p>
    <p><strong>Current Status:</strong> {complaint.status}</p>
    <p><strong>Assigned Department:</strong> {complaint.assigned_dept}</p>
    <p><strong>Last Updated:</strong> {complaint.updated_at}</p>
    
    <p>Track your complaint at: http://localhost:5000/track/{complaint.id}</p>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    # Send email logic here
    print(f"Status update sent to {citizen_email}")