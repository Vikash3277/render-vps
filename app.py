from flask import Flask, request, jsonify, send_file, Response
from openai import OpenAI
import requests
import os
import uuid
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

# ✅ Environment Variables (set in Render)
openai_api_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

client = OpenAI(api_key=openai_api_key)

# === Home ===
@app.route("/")
def home():
    return "✅ AI Voice Agent is running."

# === AI Core Endpoint ===
@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_input = request.json.get("prompt")
        if not user_input:
            return jsonify({"error": "Missing 'prompt' in request"}), 400

        # GPT Response
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}]
        )
        gpt_text = response.choices[0].message.content

        # ElevenLabs TTS
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": gpt_text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        filename = f"response_{uuid.uuid4().hex}.mp3"
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        voice_response = requests.post(tts_url, json=payload, headers=headers)

        if voice_response.status_code != 200:
            return jsonify({"error": "TTS failed", "details": voice_response.text}), 500

        with open(filename, "wb") as f:
            f.write(voice_response.content)

        return jsonify({
            "reply": gpt_text,
            "audio_url": f"/audio/{filename}"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500

# === Serve MP3s ===
@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_file(filename, mimetype="audio/mpeg")

# === Step 1: VICIdial → SIP INVITE → Twilio hits here ===
@app.route("/twilio-sip", methods=["POST"])
def handle_incoming_sip():
    to_number = request.values.get("To", "")
    print("📞 Incoming SIP call to:", to_number)

    if "@" in to_number:
        to_number = to_number.split("@")[0].replace("sip:", "")

    response = VoiceResponse()
    response.dial(
        to_number,
        action="/customer-answered",
        answer_on_bridge=True
    )
    return Response(str(response), mimetype="application/xml")

# === Step 2: Customer Answers, now connect to AI SIP ===
@app.route("/customer-answered", methods=["POST"])
def customer_answered():
    response = VoiceResponse()
    response.dial().sip("sip:immaculateaiagent@sip.twilio.com")  # ✅ Corrected
    return Response(str(response), mimetype="application/xml")

# === Step 3: AI SIP URI is called → this is the greeting ===
@app.route("/ai-greet", methods=["POST"])
def ai_greeting():
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action="/twilio-process",
        method="POST",
        timeout=5,
        speechTimeout="auto"
    )
    gather.say("Hello. How can I help you today?")
    response.append(gather)
    response.say("We did not receive any input. Goodbye.")
    return str(response)

# === Step 4: Handle speech input ===
@app.route("/twilio-process", methods=["POST"])
def twilio_process():
    user_input = request.form.get("SpeechResult", "")
    if not user_input:
        resp = VoiceResponse()
        resp.say("Sorry, I did not catch that.")
        return str(resp)

    try:
        ask_response = requests.post(
            "https://render-vps-ypjh.onrender.com/ask",
            json={"prompt": user_input}
        )
        ask_data = ask_response.json()
        audio_url = ask_data.get("audio_url")

        if not audio_url:
            raise Exception("No audio_url in AI response")

        full_audio_url = f"https://render-vps-ypjh.onrender.com{audio_url}"
        twiml = VoiceResponse()
        twiml.play(full_audio_url)
        return str(twiml)

    except Exception as e:
        print("❌ Twilio Process Error:", e)
        resp = VoiceResponse()
        resp.say("Something went wrong. Goodbye.")
        return str(resp)

# === Run App ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
