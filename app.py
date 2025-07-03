from flask import Flask, request, jsonify
from openai import OpenAI
import requests

app = Flask(__name__)

# 🔐 Replace with your actual API keys
openai_api_key = "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"
elevenlabs_api_key = "sk_1585d159abd9d6e6a28e1b3e2ce61b4f5ad3ea93d49e677d"
voice_id = "https://elevenlabs.io/app/voice-library?voiceId=ZthjuvLPty3kTMaNKVKb"

client = OpenAI(api_key=openai_api_key)

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_input = request.json.get("prompt")

        # 🔁 GPT-4 Completion
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        gpt_text = response.choices[0].message.content

        # 🎤 ElevenLabs TTS
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

        # Save voice to file
        with open("response.mp3", "wb") as f:
            f.write(voice_response.content)

        return jsonify({
            "reply": gpt_text,
            "voice_file": "response.mp3"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=10000)
