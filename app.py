from flask import Flask, request, Response, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
import os
import re

app = Flask(__name__)

# ✅ Environment variables
twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_CALLER_ID")  # Your Twilio number, e.g., +17167140779
stream_url = os.environ.get("WS_STREAM_URL")        # WebSocket URL to your media.py, e.g., wss://your-server.com/ws

client = Client(twilio_sid, twilio_token)

# ✅ Validates US and India numbers
def sanitize_number(number):
    number = number.strip()
    if number.startswith('+') and number[1:].isdigit() and 10 <= len(number[1:]) <= 15:
        return number
    return None

# ✅ Health check
@app.route("/")
def health():
    return "✅ Flask AI Voice Server is running."

# ✅ Initiates Twilio outbound call from VICIdial
@app.route("/start-call", methods=["POST"])
def start_call():
    to_number = request.values.get("To", "").strip()
    number = sanitize_number(to_number)

    if not number:
        return jsonify({"error": "Invalid number"}), 400

    try:
        print(f"📞 Calling: {number}")
        call = client.calls.create(
            to=number,
            from_=twilio_number,
            url="https://render-vps-ypjh.onrender.com/start-ai",  # <-- Replace with your real public HTTPS URL
            method="POST"
        )
        print(f"✅ Call SID: {call.sid}")
        return jsonify({"status": "initiated", "sid": call.sid})
    except Exception as e:
        print(f"❌ Twilio error: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ Called after customer picks up
@app.route("/start-ai", methods=["POST"])
def start_ai():
    print("✅ Customer answered, connecting AI stream...")

    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)

    return Response(str(response), mimetype="application/xml")

# ✅ Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
