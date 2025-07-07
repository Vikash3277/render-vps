from flask import Flask, request, jsonify, send_file, Response
from openai import OpenAI
import requests
import os
import uuid
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# ✅ ENV Variables on Render
openai_api_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

client = OpenAI(api_key=openai_api_key)


@app.route("/")
def home():
    return "✅ AI Voice Agent is running."


# === AI Core ===
@app.route("/ask", methods=["POST"])
def ask():
    try:
        prompt = request.json.get("prompt")
        if not prompt:
            return jsonify({"error": "Missing prompt"}), 400

        # ChatGPT
        chat_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        gpt_output = chat_response.choices[0].message.content

        # ElevenLabs TTS
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": gpt_output,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }

        filename = f"response_{uuid.uuid4().hex}.mp3"
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        tts_response = requests.post(tts_url, json=payload, headers=headers)

        if tts_response.status_code != 200:
            return jsonify({"error": "TTS failed", "details": tts_response.text}), 500

        with open(filename, "wb") as f:
            f.write(tts_response.content)

        return jsonify({
            "reply": gpt_output,
            "audio_url": f"/audio/{filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_file(filename, mimetype="audio/mpeg")


# === 1. Twilio receives SIP call from VICIdial
@@app.route("/twilio-voice", methods=["POST"])
def twilio_voice_entry():
    to_number = request.values.get("To", "")
    if "@" in to_number:
        to_number = to_number.split("@")[0].replace("sip:", "")

    print(f"📞 VICIdial is calling {to_number}")
    caller_id = "+447446960231"

    response = VoiceResponse()
    dial = response.dial(caller_id=caller_id, action="/customer-answered", answer_on_bridge=True)
    dial.number(to_number)
    return Response(str(response), mimetype="application/xml")



# === 2. When customer picks up, call AI SIP agent
@app.route("/customer-answered", methods=["POST"])
def customer_answered():
    response = VoiceResponse()
    response.dial().sip("sip:immaculateaiagent@sip.twilio.com")  # 👈 Your AI SIP user
    return Response(str(response), mimetype="application/xml")


# === 3. Optional (when AI listens for customer speech input)
@app.route("/twilio-process", methods=["POST"])
def twilio_process():
    speech_input = request.form.get("SpeechResult", "")
    
    if not speech_input:
        r = VoiceResponse()
        r.say("Sorry, I did not catch that.")
        return Response(str(r), mimetype="application/xml")

    try:
        r = requests.post("https://render-vps-ypjh.onrender.com/ask", json={"prompt": speech_input})
        reply = r.json()
        audio_url = reply.get("audio_url")
        if not audio_url:
            raise Exception("No audio_url in response")

        response = VoiceResponse()
        response.play(f"https://render-vps-ypjh.onrender.com{audio_url}")
        return Response(str(response), mimetype="application/xml")

    except Exception as e:
        print("Error in /twilio-process:", e)
        r = VoiceResponse()
        r.say("Something went wrong.")
        return Response(str(r), mimetype="application/xml")


# === Run App ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
