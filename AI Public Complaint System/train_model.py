import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import pickle
import os

# Sample training data
training_data = {
    'complaint_text': [
        'Road is damaged with big potholes near the market',
        'No water supply for the last 3 days in our area',
        'Garbage not collected for weeks, foul smell',
        'Street light not working on main road for a month',
        'Suspicious persons loitering in the neighborhood',
        'Broken manhole cover on sidewalk, dangerous',
        'Drainage blocked causing water logging',
        'Parking issues and traffic congestion',
        'Noise pollution from construction site',
        'Stray dogs menace in the locality'
    ],
    'category': [
        'Road', 'Water', 'Waste', 'Streetlight', 'Safety',
        'Road', 'Water', 'Traffic', 'Noise', 'Safety'
    ]
}

# Create DataFrame
df = pd.DataFrame(training_data)

# Vectorize text
vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
X = vectorizer.fit_transform(df['complaint_text'])

# Train classifier
classifier = RandomForestClassifier(n_estimators=100, random_state=42)
classifier.fit(X, df['category'])

# Save models
os.makedirs('ml_models', exist_ok=True)
with open('ml_models/complaint_classifier.pkl', 'wb') as f:
    pickle.dump(classifier, f)
with open('ml_models/vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)

print("Models trained and saved successfully!")
print(f"Classes: {classifier.classes_}")