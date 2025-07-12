from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
import re
import os

app = Flask(__name__)

# === ENV Variables ===
stream_url = os.environ.get("WS_STREAM_URL")     # e.g. wss://yourdomain.com/media

# === Helper: Validate Indian & US Numbers ===
def sanitize_number(number):
    match = re.match(r"^\+(1|91)\d{10}$", number)
    return number if match else None

# === Health Check ===
@app.route("/")
def health():
    return "✅ Flask app running."

# === Entry Point for SIP Call from VICIdial/Softphone ===
@app.route("/start-call", methods=["POST"])
def start_call():
    to_number = request.values.get("To", "")
    print(f"📞 SIP INVITE received for: {to_number}")

    # Extract phone number from SIP URI
    if "@" in to_number:
        number = to_number.split("@")[0].replace("sip:", "")
    else:
        number = to_number

    number = sanitize_number(number)
    if not number:
        print("❌ Invalid phone number format.")
        response = VoiceResponse()
        response.say("Invalid number.")
        return Response(str(response), mimetype="application/xml")

    print(f"✅ Connecting customer directly to AI via WebSocket stream: {stream_url}")

    # Build TwiML to start streaming to AI
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)

    return Response(str(response), mimetype="application/xml")

# === Run Flask App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
