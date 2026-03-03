import re
from textblob import TextBlob

def process_text(text):
    """Clean and process complaint text"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text

def extract_keywords(text):
    """Extract important keywords from complaint"""
    # Simple keyword extraction based on noun phrases
    blob = TextBlob(text)
    keywords = [phrase for phrase in blob.noun_phrases if len(phrase.split()) <= 3]
    return keywords[:5]

def analyze_sentiment(text):
    """Analyze sentiment of complaint"""
    blob = TextBlob(text)
    sentiment = blob.sentiment.polarity
    
    if sentiment < -0.5:
        return 'Very Negative'
    elif sentiment < 0:
        return 'Negative'
    elif sentiment == 0:
        return 'Neutral'
    elif sentiment < 0.5:
        return 'Positive'
    else:
        return 'Very Positive'

def extract_location(text):
    """Extract location information from text"""
    # Simple location extraction based on common patterns
    location_patterns = [
        r'near\s+([A-Za-z\s]+)',
        r'at\s+([A-Za-z\s]+)',
        r'in\s+([A-Za-z\s]+)',
        r'([A-Za-z\s]+)\s+road',
        r'([A-Za-z\s]+)\s+street'
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).strip()
    
    return None