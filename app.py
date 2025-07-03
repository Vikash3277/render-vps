from flask import Flask, request, jsonify
from openai import OpenAI
import requests
import os

app = Flask(__name__)

# ✅ Use Render Environment Variables
openai_api_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

client = OpenAI(api_key=openai_api_key)

@app.route("/")
def home():
    return "AI Voice Agent is running."

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_input = request.json.get("prompt")

        # GPT Completion
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": user_input}
            ]
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

        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        voice_response = requests.post(tts_url, json=payload, headers=headers)

        # Save as a file
        with open("response.mp3", "wb") as f:
            f.write(voice_response.content)

        return jsonify({
            "reply": gpt_text,
            "audio_url": "response.mp3"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500

# ✅ Required for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
