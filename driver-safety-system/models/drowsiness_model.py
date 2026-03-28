import cv2
import numpy as np
import dlib
from scipy.spatial import distance as dist
from imutils import face_utils

class DrowsinessDetector:
    def __init__(self):
        # Try to load dlib's face detector and landmark predictor
        try:
            self.detector = dlib.get_frontal_face_detector()
            # Use the correct path to your shape predictor file
            self.predictor = dlib.shape_predictor('models/shape_predictor_68_face_landmarks.dat')
            self.face_detection_available = True
        except Exception as e:
            print(f"Dlib initialization error: {e}")
            print("Using fallback detection method...")
            self.face_detection_available = False
            # Initialize Haar cascade as fallback
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
        
        # Eye aspect ratio threshold
        self.EYE_AR_THRESH = 0.25
        self.EYE_AR_CONSEC_FRAMES = 20
        
        # Initialize counters
        self.eye_counter = 0
        self.blink_counter = 0
        self.drowsiness_level = 0
        
        # Define eye landmarks indices if using dlib
        if self.face_detection_available:
            try:
                (self.lStart, self.lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
                (self.rStart, self.rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
            except:
                self.face_detection_available = False
    
    def eye_aspect_ratio(self, eye):
        """Calculate the eye aspect ratio"""
        A = dist.euclidean(eye[1], eye[5])
        B = dist.euclidean(eye[2], eye[4])
        C = dist.euclidean(eye[0], eye[3])
        ear = (A + B) / (2.0 * C)
        return ear
    
    def process_with_dlib(self, frame, gray):
        """Process frame using dlib"""
        faces = self.detector(gray, 0)
        data = {
            'drowsiness_level': 0,
            'eye_status': 'unknown',
            'head_position': 'unknown',
            'alert': False
        }
        
        for face in faces:
            # Get facial landmarks
            shape = self.predictor(gray, face)
            shape = face_utils.shape_to_np(shape)
            
            # Extract eye coordinates
            leftEye = shape[self.lStart:self.lEnd]
            rightEye = shape[self.rStart:self.rEnd]
            
            # Calculate eye aspect ratio
            leftEAR = self.eye_aspect_ratio(leftEye)
            rightEAR = self.eye_aspect_ratio(rightEye)
            ear = (leftEAR + rightEAR) / 2.0
            
            # Check for eye closure
            if ear < self.EYE_AR_THRESH:
                self.eye_counter += 1
                data['eye_status'] = 'closed'
                
                if self.eye_counter >= self.EYE_AR_CONSEC_FRAMES:
                    self.drowsiness_level = min(1.0, self.eye_counter / 50)
                    data['drowsiness_level'] = self.drowsiness_level
                    data['alert'] = True
            else:
                if self.eye_counter > 3:
                    self.blink_counter += 1
                self.eye_counter = 0
                data['eye_status'] = 'open'
                data['drowsiness_level'] = self.drowsiness_level * 0.9  # Gradually decrease
            
            # Draw eye contours
            leftEyeHull = cv2.convexHull(leftEye)
            rightEyeHull = cv2.convexHull(rightEye)
            cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)
            
            # Display info
            cv2.putText(frame, f"EAR: {ear:.2f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.putText(frame, f"Blinks: {self.blink_counter}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if data['drowsiness_level'] > 0.7:
                cv2.putText(frame, "DROWSINESS DETECTED!", (10, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
            elif data['drowsiness_level'] > 0.3:
                cv2.putText(frame, "FATIGUE WARNING", (10, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        return frame, data
    
    def process_with_fallback(self, frame, gray):
        """Process frame using Haar cascades as fallback"""
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        data = {
            'drowsiness_level': 0,
            'eye_status': 'unknown',
            'head_position': 'unknown',
            'alert': False
        }
        
        for (x, y, w, h) in faces:
            # Draw face rectangle
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
            # Region of interest for eyes
            roi_gray = gray[y:y+h, x:x+w]
            roi_color = frame[y:y+h, x:x+w]
            
            # Detect eyes
            eyes = self.eye_cascade.detectMultiScale(roi_gray)
            
            if len(eyes) >= 2:
                data['eye_status'] = 'open'
                data['drowsiness_level'] = max(0, data['drowsiness_level'] - 0.1)
                
                # Draw rectangles around eyes
                for (ex, ey, ew, eh) in eyes[:2]:  # Draw first two eyes
                    cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 2)
            else:
                self.eye_counter += 1
                data['eye_status'] = 'closed'
                data['drowsiness_level'] = min(1.0, self.eye_counter / 30)
                
                if data['drowsiness_level'] > 0.7:
                    data['alert'] = True
            
            # Display info
            cv2.putText(frame, f"Eyes: {data['eye_status']}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Drowsiness: {data['drowsiness_level']*100:.1f}%", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame, data
    
    def process_frame(self, frame):
        """Process a single frame for drowsiness detection"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.face_detection_available:
            return self.process_with_dlib(frame, gray)
        else:
            return self.process_with_fallback(frame, gray)