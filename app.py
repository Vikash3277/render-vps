from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Dial, Connect, Stream
import re
import os

app = Flask(__name__)

# === ENV Variables ===
stream_url = os.environ.get("WS_STREAM_URL")  # e.g. wss://yourdomain.com/ws

# === Helper: Validate Indian & US Numbers ===
def sanitize_number(number):
    match = re.match(r"^\+(1|91)\d{10}$", number)
    return number if match else None

# === Health Check ===
@app.route("/")
def health():
    return "✅ Flask app running."

# === Entry Point for VICIdial SIP Call ===
@app.route("/start-call", methods=["POST"])
def start_call():
    to_number = request.values.get("To", "")
    print(f"📞 SIP INVITE received for: {to_number}")

    # Extract number from SIP URI if needed
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

    # Build TwiML to dial customer first
    response = VoiceResponse()
    dial = Dial(action="/start-ai")  # Twilio will hit this after customer answers
    dial.number(number)
    response.append(dial)

    print(f"📲 Dialing customer: {number}, will start AI after pickup")
    return Response(str(response), mimetype="application/xml")

# === When Customer Picks Up ===
@app.route("/start-ai", methods=["POST"])
def start_ai():
    print("✅ Customer answered, starting AI stream...")
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)
    return Response(str(response), mimetype="application/xml")

# === Run Flask App ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
