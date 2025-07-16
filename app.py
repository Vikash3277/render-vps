from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather, Play
import openai
import os
import aiohttp
import uuid

app = Flask(__name__)

# ✅ API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID")

# Store audio replies in memory or temp files
audio_responses = {}

@app.route("/", methods=["GET"])
def home():
    return "✅ Dispatch AI with ElevenLabs running."

# === Step 1: AI Sales Pitch with ElevenLabs voice ===
@app.route("/voice", methods=["POST"])
def voice():
    response = VoiceResponse()

    # Generate ElevenLabs TTS and store
    intro_text = (
        "Hello! This is DispatchPro. We help truckers like you find high-paying loads "
        "and handle paperwork. For a $4000 load, we only charge $50. "
        "Do you have any questions about our dispatch service?"
    )
    audio_url = generate_tts_and_store(intro_text)

    # Use <Play> to stream the audio
    response.play(audio_url)

    # Gather speech input
    gather = Gather(input="speech", timeout=5, speech_timeout="auto", action="/process", method="POST")
    gather.say("Please say your question now.")
    response.append(gather)

    response.redirect("/voice")
    return Response(str(response), mimetype="application/xml")

# === Step 2: Respond to user question ===
@app.route("/process", methods=["POST"])
def process():
    speech_result = request.form.get("SpeechResult", "")
    print(f"🗣️ Trucker: {speech_result}")

    gpt_reply = "I'm sorry, could you repeat that?"

    try:
        prompt = f"A trucker asked: '{speech_result}'. Respond with a helpful dispatch sales reply. For a $4000 load, the fee is $50."
        chat = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful dispatch assistant who explains the service, fees, and responds to trucking-related questions."},
                {"role": "user", "content": prompt}
            ]
        )
        gpt_reply = chat.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ GPT error: {e}")

    # Generate ElevenLabs audio from GPT reply
    audio_url = generate_tts_and_store(gpt_reply)

    response = VoiceResponse()
    response.play(audio_url)

    gather = Gather(input="speech", timeout=5, speech_timeout="auto", action="/process", method="POST")
    gather.say("Do you have another question?")
    response.append(gather)

    response.redirect("/voice")
    return Response(str(response), mimetype="application/xml")

# === Step 3: Generate and serve ElevenLabs audio ===
def generate_tts_and_store(text):
    audio_id = str(uuid.uuid4())
    audio_path = f"/tmp/{audio_id}.mp3"

    try:
        import requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "use_speaker_boost": True
            }
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            with open(audio_path, "wb") as f:
                f.write(response.content)
            print(f"🎧 Saved TTS to {audio_path}")
            return f"/audio/{audio_id}"  # serve it from Flask route
        else:
            print("❌ ElevenLabs error:", response.text)
    except Exception as e:
        print(f"❌ TTS generation failed: {e}")

    return None

# === Step 4: Serve the audio file to Twilio ===
@app.route("/audio/<audio_id>", methods=["GET"])
def serve_audio(audio_id):
    path = f"/tmp/{audio_id}.mp3"
    if os.path.exists(path):
        return send_file(path, mimetype="audio/mpeg")
    else:
        return "Audio not found", 404

# === Run ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
