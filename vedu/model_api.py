from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import joblib
import PyPDF2
import io
import re
from datetime import datetime
from LEGAL_JARGONS import LEGAL_JARGONS

app = Flask(__name__)
CORS(app)

# Path resolution function
def find_model_path():
    """Find the model file in various possible locations"""
    possible_paths = [
        # Direct path in current directory
        os.path.join("models", "saved_model.pkl"),
        # Path from vedu directory
        os.path.join("Model", "models", "saved_model.pkl"),
        # Path if running from scripts folder
        os.path.join("..", "models", "saved_model.pkl"),
        # Absolute path patterns
        os.path.join(os.getcwd(), "models", "saved_model.pkl"),
        os.path.join(os.getcwd(), "Model", "models", "saved_model.pkl"),
        # Check parent directory
        os.path.join(os.path.dirname(os.getcwd()), "models", "saved_model.pkl"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Model found at: {path}")
            return path
    
    print("❌ Model file 'saved_model.pkl' not found in any expected location.")
    print("Checked paths:")
    for path in possible_paths:
        print(f"  - {path}")
    return None

# Find and set model path
MODEL_PATH = find_model_path()
UPLOAD_FOLDER = "temp_uploads"

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load model at startup
vectorizer, clf = None, None
if MODEL_PATH:
    try:
        vectorizer, clf = joblib.load(MODEL_PATH)
        print("✅ Model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        vectorizer, clf = None, None
else:
    print("🔄 Running without model - will use basic classification")

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def extract_jargons_from_text(text):
    """Extract legal jargons from text with their meanings and occurrences"""
    jargons_found = {}
    text_lower = text.lower()
    
    for jargon, meaning in LEGAL_JARGONS.items():
        # Count occurrences (case insensitive)
        pattern = re.compile(re.escape(jargon.lower()), re.IGNORECASE)
        matches = pattern.findall(text_lower)
        
        if matches:
            jargons_found[jargon] = {
                "meaning": meaning,
                "occurrences": len(matches),
                "original_term": jargon
            }
    
    return jargons_found

def simplify_text_with_jargons(text, jargons_found):
    """Replace jargons in text with simplified explanations"""
    simplified_text = text
    
    for jargon, info in jargons_found.items():
        # Replace each occurrence with jargon + explanation in parentheses
        pattern = re.compile(re.escape(jargon), re.IGNORECASE)
        replacement = f"{jargon} ({info['meaning']})"
        simplified_text = pattern.sub(replacement, simplified_text, count=1)  # Replace first occurrence
    
    return simplified_text

def extract_key_terms(text):
    """Extract key terms from document text"""
    # Simple keyword extraction - you can enhance this
    key_terms = []
    
    # Common legal keywords to look for
    legal_keywords = [
        "agreement", "contract", "party", "parties", "obligation", "liability",
        "terms", "conditions", "payment", "delivery", "breach", "termination",
        "confidentiality", "intellectual property", "damages", "indemnity"
    ]
    
    text_lower = text.lower()
    for keyword in legal_keywords:
        if keyword in text_lower:
            key_terms.append(keyword.title())
    
    return key_terms[:10]  # Return top 10

def extract_dates(text):
    """Extract important dates from text"""
    dates = []
    
    # Simple date pattern matching
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{1,2}\s+\w+\s+\d{4}\b',
        r'\b\w+\s+\d{1,2},?\s+\d{4}\b'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            dates.append({"type": "General", "date": match})
    
    return dates[:5]  # Return first 5 dates found

def extract_parties(text):
    """Extract party names from document"""
    parties = []
    
    # Look for common patterns like "Party A", "The Company", etc.
    party_patterns = [
        r'\b(?:Party|PARTY)\s+[A-Z]\b',
        r'\b(?:The|THE)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Company|Corporation|LLC|Inc\.?|Ltd\.?)\b',
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Company|Corporation|LLC|Inc\.?|Ltd\.?)\b'
    ]
    
    for pattern in party_patterns:
        matches = re.findall(pattern, text)
        parties.extend(matches)
    
    return list(set(parties))[:5]  # Return unique parties, max 5

def analyze_complexity(jargons_found, total_words):
    """Analyze document complexity based on jargon density"""
    jargon_count = len(jargons_found)
    
    if total_words == 0:
        return {"complexity": "Unknown", "score": 0, "jargonCount": 0, "totalWords": 0}
    
    jargon_density = (jargon_count / total_words) * 100
    
    if jargon_density < 1:
        complexity = "Low"
    elif jargon_density < 3:
        complexity = "Medium"
    else:
        complexity = "High"
    
    return {
        "complexity": complexity,
        "score": round(jargon_density, 2),
        "jargonCount": jargon_count,
        "totalWords": total_words
    }

def generate_jargon_summary(jargons_found):
    """Generate a summary of jargons found"""
    if not jargons_found:
        return "This document contains minimal legal jargon and should be easy to understand."
    
    total_jargons = len(jargons_found)
    
    if total_jargons == 1:
        return f"This document contains 1 legal term that has been simplified for better understanding."
    else:
        return f"This document contains {total_jargons} legal terms that have been identified and simplified for better understanding. The most complex terms relate to legal obligations, rights, and procedures."

def classify_document_type(text):
    """Basic document classification based on keywords"""
    text_lower = text.lower()
    
    # Employment related keywords
    employment_keywords = ['employment', 'employee', 'employer', 'salary', 'wages', 'job', 'work', 'hire', 'firing', 'termination', 'benefits']
    employment_score = sum(1 for keyword in employment_keywords if keyword in text_lower)
    
    # Contract keywords
    contract_keywords = ['contract', 'agreement', 'parties', 'terms', 'conditions', 'obligations', 'breach', 'performance']
    contract_score = sum(1 for keyword in contract_keywords if keyword in text_lower)
    
    # Service agreement keywords
    service_keywords = ['service', 'services', 'provider', 'client', 'deliverables', 'scope', 'work']
    service_score = sum(1 for keyword in service_keywords if keyword in text_lower)
    
    # NDA keywords
    nda_keywords = ['confidential', 'non-disclosure', 'proprietary', 'trade secret', 'confidentiality']
    nda_score = sum(1 for keyword in nda_keywords if keyword in text_lower)
    
    # Sales agreement keywords
    sales_keywords = ['purchase', 'sale', 'buy', 'sell', 'goods', 'products', 'delivery', 'payment']
    sales_score = sum(1 for keyword in sales_keywords if keyword in text_lower)
    
    # Lease agreement keywords
    lease_keywords = ['lease', 'rent', 'tenant', 'landlord', 'property', 'premises', 'monthly']
    lease_score = sum(1 for keyword in lease_keywords if keyword in text_lower)
    
    # Determine document type based on highest score
    scores = {
        'Employment Agreement': employment_score,
        'Service Agreement': service_score,
        'Non-Disclosure Agreement': nda_score,
        'Sales Agreement': sales_score,
        'Lease Agreement': lease_score,
        'General Contract': contract_score
    }
    
    # Get the classification with highest score
    classification = max(scores.items(), key=lambda x: x[1])
    
    # Calculate confidence based on score
    total_score = sum(scores.values())
    confidence = classification[1] / max(total_score, 1) if total_score > 0 else 0.5
    
    return classification[0], min(confidence, 0.95)  # Cap confidence at 95%

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    model_status = "loaded" if (vectorizer is not None and clf is not None) else "not loaded"
    return jsonify({
        "status": "healthy",
        "service": "model-api",
        "model_status": model_status,
        "model_path": MODEL_PATH,
        "jargon_terms": len(LEGAL_JARGONS),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/classify', methods=['POST'])
def classify_document():
    """Main endpoint for document classification and jargon analysis"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"success": False, "error": "Only PDF files are supported"}), 400
        
        # Extract text from PDF
        text = extract_text_from_pdf(file)
        if not text:
            return jsonify({"success": False, "error": "Could not extract text from PDF"}), 400
        
        # Perform jargon analysis
        jargons_found = extract_jargons_from_text(text)
        simplified_text = simplify_text_with_jargons(text, jargons_found) if jargons_found else text
        
        # Calculate complexity
        total_words = len(text.split())
        complexity_analysis = analyze_complexity(jargons_found, total_words)
        jargon_summary = generate_jargon_summary(jargons_found)
        
        # Document classification
        if vectorizer is not None and clf is not None:
            try:
                # Use trained model for classification
                text_vectorized = vectorizer.transform([text])
                prediction = clf.predict(text_vectorized)[0]
                confidence_scores = clf.predict_proba(text_vectorized)[0]
                classification = prediction
                confidence = float(max(confidence_scores))
            except Exception as e:
                print(f"Model prediction error: {e}")
                # Fall back to keyword-based classification
                classification, confidence = classify_document_type(text)
        else:
            # Use keyword-based classification
            classification, confidence = classify_document_type(text)
        
        # Extract additional information
        key_terms = extract_key_terms(text)
        important_dates = extract_dates(text)
        parties_involved = extract_parties(text)
        
        # Generate summary
        summary = f"This appears to be a {classification.lower()} containing {len(jargons_found)} legal terms. "
        if jargons_found:
            summary += f"Key legal concepts include: {', '.join(list(jargons_found.keys())[:3])}."
        
        response_data = {
            "success": True,
            "classification": classification,
            "confidence": confidence,
            "key_terms": key_terms,
            "summary": summary,
            "important_dates": important_dates,
            "parties_involved": parties_involved,
            "jargon_analysis": {
                "jargons_found": jargons_found,
                "simplified_text": simplified_text,
                "total_jargons": len(jargons_found),
                "jargon_summary": jargon_summary,
                "complexity_analysis": complexity_analysis
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in classify_document: {e}")
        return jsonify({
            "success": False, 
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route('/simplify-jargons', methods=['POST'])
def simplify_jargons():
    """Endpoint for standalone jargon simplification"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"success": False, "error": "No text provided"}), 400
        
        text = data['text']
        if not text.strip():
            return jsonify({"success": False, "error": "Empty text provided"}), 400
        
        # Perform jargon analysis
        jargons_found = extract_jargons_from_text(text)
        simplified_text = simplify_text_with_jargons(text, jargons_found) if jargons_found else text
        
        # Calculate complexity
        total_words = len(text.split())
        complexity_analysis = analyze_complexity(jargons_found, total_words)
        jargon_summary = generate_jargon_summary(jargons_found)
        
        response_data = {
            "success": True,
            "original_text": text,
            "simplified_text": simplified_text,
            "jargons_found": jargons_found,
            "total_jargons": len(jargons_found),
            "complexity_analysis": complexity_analysis,
            "jargon_summary": jargon_summary
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in simplify_jargons: {e}")
        return jsonify({
            "success": False, 
            "error": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Model API Server...")
    print(f"Model Status: {'✅ Loaded' if (vectorizer and clf) else '❌ Not Loaded'}")
    print(f"Legal Jargons Dictionary: {len(LEGAL_JARGONS)} terms loaded")
    if MODEL_PATH:
        print(f"Model Path: {MODEL_PATH}")
    app.run(host='0.0.0.0', port=5001, debug=True)