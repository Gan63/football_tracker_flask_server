import sys
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
import base64
import requests   # ✅ REQUIRED FOR MCP COMMUNICATION

# 🔴 REMOVED: from football_core import tracker_api  (not needed here)

# ============================================================
# BASIC SETUP
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='frontend', static_folder='frontend', static_url_path='/')
CORS(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

processing_status = {"status": "idle", "progress": 0, "message": "Ready"}
current_tracking_data = None

# ============================================================
# BASIC HELPERS
# ============================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# HOME ROUTES
# ============================================================

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        return f"Error loading page: {e}", 500


# ============================================================
# ⚡ UPLOAD + SEND TO MCP SERVER
# ============================================================

@app.route('/upload', methods=['GET', 'POST'])
def upload_video():
    if request.method == 'POST':
        logger.info("Received POST request to /upload")

        if 'video' not in request.files:
            return jsonify({"error": "No video provided"}), 400

        file = request.files['video']

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400

        # Save file locally
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"

        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        logger.info(f"File saved at {filepath}")

        # ====================================================
        # 🔥 SEND FILE TO MCP SERVER (Flask API on Render)
        # ====================================================
        try:
            with open(filepath, "rb") as f:
                video_base64 = base64.b64encode(f.read()).decode()

            # ⚠️ Payload shape – match MCP API (no "input" wrapper)
            payload = {
                "video_base64": video_base64
            }

            # ✅ Call the correct endpoint on your MCP API
            response = requests.post(
                "https://football-tracker-mcp.onrender.com/run-tracking",
                json=payload,
                timeout=600  # allow long processing
            )

            # If MCP itself failed (500, 404, etc.)
            if not response.ok:
                logger.error(f"MCP HTTP error: {response.status_code} {response.text}")
                return jsonify({"error": f"MCP HTTP error: {response.status_code}"}), 500

            data = response.json()
            logger.info(f"MCP response: {data.keys()}")

            if data.get("status") == "success":
                # Save processed output from MCP
                output_path = os.path.join(OUTPUT_FOLDER, "mcp_output.mp4")
                if "output_video_base64" not in data:
                    return jsonify({"error": "MCP response missing 'output_video_base64'"}), 500

                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(data["output_video_base64"]))

                # tracking_data might be missing – handle gracefully
                tracking = data.get("tracking_data")

                return jsonify({
                    "message": "Processing completed via MCP",
                    "tracking_data": tracking,
                    "output_video": "mcp_output.mp4"
                })

            else:
                return jsonify({"error": data.get("message", "Unknown MCP error")}), 500

        except Exception as e:
            logger.error(f"MCP ERROR: {e}")
            return jsonify({"error": f"MCP connection failed: {str(e)}"}), 500

    # GET → return upload page
    try:
        return render_template('upload.html')
    except Exception as e:
        logger.error(f"Error rendering upload.html: {e}")
        return f"Error loading upload page: {e}", 500


# ============================================================
# API STATUS
# ============================================================

@app.route('/api/status')
def get_status():
    return jsonify(processing_status)


# ============================================================
# GET TRACKING DATA (if you store it later)
# ============================================================

@app.route('/api/tracking-data')
def get_tracking_data():
    if current_tracking_data:
        return jsonify(current_tracking_data)
    return jsonify({"error": "No tracking data available"}), 404


# ============================================================
# DOWNLOAD OUTPUT VIDEO
# ============================================================

@app.route('/download/<path:filename>')
def download_file(filename):
    safe = secure_filename(filename)
    return send_from_directory(OUTPUT_FOLDER, safe)


# ============================================================
# SYSTEM INFO
# ============================================================

@app.route('/api/system-info')
def system_info():
    return jsonify({
        "python": sys.version,
        "platform": sys.platform,
        "upload_folder": os.path.exists(UPLOAD_FOLDER),
        "output_folder": os.path.exists(OUTPUT_FOLDER)
    })


# ============================================================
# MAIN ENTRY (local only – Render uses gunicorn)
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MCP-ENABLED FOOTBALL TRACKER — FLASK SERVER")
    print("=" * 60)
    print("🌐 Running at: http://localhost:5000")
    print("🔗 Connected to MCP Server at: https://football-tracker-mcp.onrender.com/run-tracking")
    print("=" * 60)

    app.run(debug=False, host='0.0.0.0', port=5000)
