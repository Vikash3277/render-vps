from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import requests
import os
import uuid
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

# ✅ Use Render Environment Variables
openai_api_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

client = OpenAI(api_key=openai_api_key)

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

        # GPT Completion
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

        # Generate unique filename
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

# === Serve MP3 files ===
@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_file(filename, mimetype="audio/mpeg")

# === Twilio Voice Webhook ===
@app.route("/twilio-voice", methods=["POST"])
def twilio_voice():
    """Initial webhook that Twilio hits when the call starts."""
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

# === Twilio Speech Result Handler ===
@app.route("/twilio-process", methods=["POST"])
def twilio_process():
    """Handles speech input from Twilio and returns AI voice response."""
    user_input = request.form.get("SpeechResult", "")
    if not user_input:
        resp = VoiceResponse()
        resp.say("Sorry, I did not catch that.")
        return str(resp)

    try:
        # Send to AI agent
        ask_response = requests.post(
            "https://render-vps-ypjh.onrender.com/ask",  # 👈 replace with your live URL
            json={"prompt": user_input}
        )
        ask_data = ask_response.json()
        audio_url = ask_data.get("audio_url")

        if not audio_url:
            raise Exception("No audio_url in AI response")

        full_audio_url = f"https://render-vps-ypjh.onrender.com{audio_url}"  # 👈 replace

        # Return TwiML to play audio
        twiml = VoiceResponse()
        twiml.play(full_audio_url)
        return str(twiml)

    except Exception as e:
        print("❌ Twilio Process Error:", e)
        resp = VoiceResponse()
        resp.say("Something went wrong. Goodbye.")
        return str(resp)

# ✅ Required for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
