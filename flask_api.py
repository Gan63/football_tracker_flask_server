import sys
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
import base64
import requests   # required to call MCP

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
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
app.config['SECRET_KEY'] = 'your-secret-key-here'

processing_status = {"status": "idle", "progress": 0, "message": "Ready"}
current_tracking_data = None


# ============================================================
# HELPERS
# ============================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# HOME PAGE
# ============================================================

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error loading index.html: {e}")
        return f"Error loading page: {e}", 500


# ============================================================
# 🚀 UPLOAD + SEND VIDEO TO MCP SERVER
# ============================================================

@app.route('/upload', methods=['GET', 'POST'])
def upload_video():
    if request.method == 'POST':
        logger.info("Received POST request at /upload")

        if 'video' not in request.files:
            return jsonify({"error": "No video file sent"}), 400

        file = request.files['video']

        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400

        # Save uploaded video
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"

        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        logger.info(f"File saved at {filepath}")

        # Convert video to Base64
        try:
            with open(filepath, "rb") as f:
                video_base64 = base64.b64encode(f.read()).decode()
        except Exception as e:
            logger.error(f"Base64 encoding failed: {e}")
            return jsonify({"error": "Failed to encode video"}), 500

        # Prepare payload
        payload = {
            "video_base64": video_base64
        }

        # ====================================================
        # 🔥 Send request to MCP server
        # ====================================================
        try:
            response = requests.post(
                "https://clamboy-football-tracker-mcp.hf.space/run-tracking",
                json=payload,
                timeout=600   # long timeout for video processing
            )

            if not response.ok:
                logger.error(f"MCP error: {response.status_code} {response.text}")
                return jsonify({"error": "MCP returned an error"}), 500

            mcp_result = response.json()
            logger.info(f"MCP response keys: {list(mcp_result.keys())}")

            if mcp_result.get("status") != "success":
                return jsonify({"error": mcp_result.get("message", "Unknown MCP error")}), 500

            # Save processed output video
            if "output_video_base64" in mcp_result:
                output_path = os.path.join(OUTPUT_FOLDER, "mcp_output.mp4")
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(mcp_result["output_video_base64"]))

            tracking_data = mcp_result.get("tracking_data")

            return jsonify({
                "message": "Processing successful via MCP",
                "tracking_data": tracking_data,
                "output_video": "mcp_output.mp4"
            })

        except Exception as e:
            logger.error(f"MCP connection ERROR: {e}")
            return jsonify({"error": f"MCP connection failed: {str(e)}"}), 500

    # GET request shows upload page
    try:
        return render_template('upload.html')
    except Exception as e:
        logger.error(f"Error rendering upload.html: {e}")
        return f"Error loading page: {e}", 500


# ============================================================
# STATUS API
# ============================================================

@app.route('/api/status')
def get_status():
    return jsonify(processing_status)


# ============================================================
# TRACKING DATA (optional)
# ============================================================

@app.route('/api/tracking-data')
def get_tracking_data():
    if current_tracking_data:
        return jsonify(current_tracking_data)
    return jsonify({"error": "No tracking data available"}), 404


# ============================================================
# DOWNLOAD OUTPUT
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
        "upload_folder_exists": os.path.exists(UPLOAD_FOLDER),
        "output_folder_exists": os.path.exists(OUTPUT_FOLDER)
    })


# ============================================================
# LOCAL RUN ONLY
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 FOOTBALL TRACKER — FLASK FRONTEND API")
    print("🌐 http://localhost:5000")
    print("=" * 60)

    app.run(debug=False, host='0.0.0.0', port=5000)
