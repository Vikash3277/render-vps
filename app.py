from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial, Connect, Stream
import re
import os

app = Flask(__name__)

# === ENV Variables ===
twilio_number = os.environ.get("TWILIO_NUMBER")  # e.g. +14155551234
stream_url = os.environ.get("WS_STREAM_URL")     # e.g. wss://yourdomain.com/media

# === Helper: Validate Indian & US Numbers ===
def sanitize_number(number):
    match = re.match(r"^\+(1|91)\d{10}$", number)
    return number if match else None

# === Health Check ===
@app.route("/")
def health():
    return "✅ Flask app running."

# === Start Call from VICIdial (via Twilio SIP) ===
@app.route("/start-call", methods=["POST"])
def start_call():
    to_number = request.values.get("To", "")
    print(f"📞 Raw number from Twilio: {to_number}")

    # Extract number from SIP URI (e.g., sip:+919876543210@sip.yourdomain.com)
    if "@" in to_number:
        number = to_number.split("@")[0].replace("sip:", "")
    else:
        number = to_number

    number = sanitize_number(number)
    if not number:
        print("❌ Invalid phone number format.")
        response = VoiceResponse()
        response.say("Invalid number. Goodbye.")
        return Response(str(response), mimetype="application/xml")

    print(f"✅ Dialing number: {number}")

    response = VoiceResponse()
    dial = Dial(
        caller_id=twilio_number,
        answer_on_bridge=True
    )
    # When customer answers, Twilio calls /connect-ai to start WebSocket media stream
    dial.number(number, url="/connect-ai")
    response.append(dial)

    return Response(str(response), mimetype="application/xml")

# === After Customer Answers: Start Media Stream to AI Agent ===
@app.route("/connect-ai", methods=["POST"])
def connect_ai():
    print("✅ Customer answered. Connecting to AI WebSocket")

    response = VoiceResponse()
    connect = Connect()
    
    # ✅ Only one <Stream> tag is valid
    connect.stream(url=stream_url)

    response.append(connect)

    return Response(str(response), mimetype="application/xml")

# === Run Flask App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
