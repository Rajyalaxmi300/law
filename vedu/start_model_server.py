#!/usr/bin/env python3
"""
Startup script for the Legal Document AI Model Server
This script sets up and starts the Flask API server for document classification and jargon analysis
"""

import os
import sys
import subprocess

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import flask
        import flask_cors
        import joblib
        import PyPDF2
        import sklearn
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False

def check_model_files():
    """Check if model files exist"""
    model_path = os.path.join("vedu","models", "saved_model.pkl")
    jargons_path = "LEGAL_JARGONS.py"
    
    if not os.path.exists(model_path):
        print(f"⚠️  Model file not found at {model_path}")
        print("The server will run with basic classification functionality")
        return False
    
    if not os.path.exists(jargons_path):
        print(f"❌ LEGAL_JARGONS.py not found")
        return False
    
    print("✅ All required files found")
    return True

def main():
    """Main startup function"""
    print("🚀 Legal Document AI Model Server Startup")
    print("=" * 50)
    
    # Change to the correct directory (vedu folder)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check model files
    check_model_files()
    
    # Start the Flask server
    print("\n🌟 Starting Flask API Server on http://localhost:5001")
    print("📊 Available endpoints:")
    print("  - GET  /health - Health check")
    print("  - POST /classify - Document classification and jargon analysis")
    print("  - POST /simplify-jargons - Standalone jargon simplification")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Import and run the Flask app
        from model_api import app
        app.run(host='0.0.0.0', port=5001, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()