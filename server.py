#!/usr/bin/env python3

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)

# ----------------------
# STATE
# ----------------------
active_beds = {}      # bed_id -> timestamp
lock = threading.Lock()

BED_ID = "bed-1"      # Change this per device/room

# ----------------------
# HTML INTERFACE (Phone)
# ----------------------
PHONE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nurse Call - Bed {{ bed_id }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a202c;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 30px;
            padding: 20px;
        }
        h1 { color: #fff; font-size: 1.5rem; text-align: center; }
        .bed-label { color: #a0aec0; font-size: 0.9rem; margin-bottom: 10px; }
        
        .btn {
            width: 200px;
            height: 200px;
            border-radius: 50%;
            border: none;
            font-size: 1.3rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 8px;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        .btn:active { transform: scale(0.95); }
        
        .btn-red {
            background: linear-gradient(145deg, #e53e3e, #c53030);
            color: white;
            box-shadow: 0 10px 30px rgba(229, 62, 62, 0.4);
        }
        .btn-red:hover { box-shadow: 0 15px 40px rgba(229, 62, 62, 0.6); }
        .btn-red:disabled {
            background: #4a5568;
            box-shadow: none;
            cursor: not-allowed;
        }
        
        .btn-green {
            background: linear-gradient(145deg, #38a169, #2f855a);
            color: white;
            box-shadow: 0 10px 30px rgba(56, 161, 105, 0.4);
        }
        .btn-green:hover { box-shadow: 0 15px 40px rgba(56, 161, 105, 0.6); }
        .btn-green:disabled {
            background: #4a5568;
            box-shadow: none;
            cursor: not-allowed;
        }
        
        .status {
            color: #a0aec0;
            font-size: 1rem;
            margin-top: 20px;
            text-align: center;
        }
        .status.active { color: #f56565; font-weight: bold; }
        .status.cleared { color: #48bb78; font-weight: bold; }
        
        .icon { font-size: 2.5rem; }
    </style>
</head>
<body>
    <div>
        <div class="bed-label">Room / Bed</div>
        <h1>{{ bed_id }}</h1>
    </div>
    
    <button id="callBtn" class="btn btn-red" onclick="callNurse()">
        <span class="icon">🔴</span>
        <span>CALL NURSE</span>
    </button>
    
    <button id="clearBtn" class="btn btn-green" onclick="clearCall()" disabled>
        <span class="icon">✅</span>
        <span>ALL CLEAR</span>
    </button>
    
    <div id="status" class="status">Tap red button to call nurse</div>

    <script>
        const bedId = "{{ bed_id }}";
        const API_URL = window.location.origin;
        
        let isCalling = false;
        
        async function callNurse() {
            try {
                const res = await fetch(`${API_URL}/api/call`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({bed_id: bedId})
                });
                const data = await res.json();
                updateUI(data.active);
            } catch(e) {
                showStatus("Error connecting to server", "error");
            }
        }
        
        async function clearCall() {
            try {
                const res = await fetch(`${API_URL}/api/clear`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({bed_id: bedId})
                });
                const data = await res.json();
                updateUI(data.active);
            } catch(e) {
                showStatus("Error connecting to server", "error");
            }
        }
        
        function updateUI(activeBeds) {
            const isActive = activeBeds.includes(bedId);
            isCalling = isActive;
            
            document.getElementById('callBtn').disabled = isActive;
            document.getElementById('clearBtn').disabled = !isActive;
            
            const status = document.getElementById('status');
            if (isActive) {
                status.textContent = "🔔 Nurse has been called!";
                status.className = "status active";
            } else {
                status.textContent = "✅ All clear - tap red to call";
                status.className = "status cleared";
            }
        }
        
        function showStatus(msg, type) {
            const status = document.getElementById('status');
            status.textContent = msg;
            status.className = "status " + (type || "");
        }
        
        // Poll for status every 2 seconds (in case cleared from elsewhere)
        setInterval(async () => {
            try {
                const res = await fetch(`${API_URL}/api/calls`);
                const data = await res.json();
                updateUI(data.beds);
            } catch(e) {}
        }, 2000);
    </script>
</body>
</html>
"""

# ----------------------
# ROUTES
# ----------------------

@app.route("/")
def index():
    return render_template_string(PHONE_HTML, bed_id=BED_ID)


@app.route("/api/calls")
def get_calls():
    with lock:
        beds = list(active_beds.keys())
    return jsonify({"beds": beds})


@app.route("/api/call", methods=["POST"])
def call_nurse():
    data = request.get_json() or {}
    bed_id = data.get("bed_id", BED_ID)
    
    with lock:
        active_beds[bed_id] = datetime.now().isoformat()
        beds = list(active_beds.keys())
    
    print(f"🚨 NURSE CALLED: {bed_id}")
    return jsonify({"status": "called", "bed_id": bed_id, "active": beds})


@app.route("/api/clear", methods=["POST"])
def clear_call():
    data = request.get_json() or {}
    bed_id = data.get("bed_id", BED_ID)
    
    with lock:
        if bed_id in active_beds:
            del active_beds[bed_id]
        beds = list(active_beds.keys())
    
    print(f"✅ CLEARED: {bed_id}")
    return jsonify({"status": "cleared", "bed_id": bed_id, "active": beds})


@app.route("/api/clear-all", methods=["POST"])
def clear_all():
    with lock:
        active_beds.clear()
    
    print("✅ ALL CLEARED")
    return jsonify({"status": "cleared_all", "active": []})


# ----------------------
# START
# ----------------------
if __name__ == "__main__":
    # Use 0.0.0.0 to accept connections from anywhere
    app.run(host="0.0.0.0", port=5000, debug=True)
