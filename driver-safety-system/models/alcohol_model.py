import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import random

class AlcoholDetector:
    def __init__(self):
        self.model = self.create_model()
        self.threshold = 0.08  # Legal BAC limit
        self.sensor_data_buffer = []
        
    def create_model(self):
        """Create and train a simple model for alcohol detection"""
        # This would normally be trained on real sensor data
        # For demo purposes, we'll create a simple threshold-based detector
        return RandomForestClassifier(n_estimators=10)
    
    def analyze(self, sensor_data):
        """
        Analyze alcohol level from sensor data
        Simulated for demo - in real app, would process actual sensor readings
        """
        # Simulate alcohol detection (replace with actual sensor logic)
        simulated_alcohol_level = self.simulate_alcohol_detection(sensor_data)
        
        # Add to buffer for trend analysis
        self.sensor_data_buffer.append(simulated_alcohol_level)
        if len(self.sensor_data_buffer) > 10:
            self.sensor_data_buffer.pop(0)
        
        # Calculate rolling average
        avg_alcohol = np.mean(self.sensor_data_buffer)
        
        return avg_alcohol
    
    def simulate_alcohol_detection(self, sensor_data):
        """Simulate alcohol detection (for demo purposes)"""
        # In real application, this would process actual sensor data
        # from breathalyzer or other alcohol sensors
        
        # Simulate random variation with bias
        base_level = sensor_data.get('base_reading', 0.02)
        variation = random.uniform(-0.01, 0.03)
        
        alcohol_level = max(0, base_level + variation)
        return alcohol_level
    
    def check_intoxication(self, alcohol_level):
        """Check if driver is intoxicated"""
        return alcohol_level >= self.threshold
    
    def get_risk_level(self, alcohol_level):
        """Get risk level based on alcohol level"""
        if alcohol_level < 0.02:
            return "Safe"
        elif alcohol_level < 0.05:
            return "Low"
        elif alcohol_level < 0.08:
            return "Moderate"
        else:
            return "High - Intoxicated"