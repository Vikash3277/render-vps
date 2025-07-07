from flask import Flask, request, jsonify, send_file, Response
from openai import OpenAI
import requests
import os
import uuid
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# ✅ ENV Variables
openai_api_key = os.environ.get("OPENAI_API_KEY")
elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")

client = OpenAI(api_key=openai_api_key)


@app.route("/")
def home():
    return "✅ AI Voice Agent is running."


# === AI Chat + TTS ===
@app.route("/ask", methods=["POST"])
def ask():
    try:
        prompt = request.json.get("prompt")
        if not prompt:
            return jsonify({"error": "Missing prompt"}), 400

        # GPT-3.5 Chat
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


# === 1. VICIdial → Twilio SIP call →
@app.route("/twilio-voice", methods=["POST"])
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


# === 2. When customer answers → AI greets and listens
@app.route("/customer-answered", methods=["POST"])
def customer_answered():
    try:
        prompt = "Hello! This is your AI assistant. How can I help you today?"

        # Call GPT + ElevenLabs
        r = requests.post("https://render-vps-ypjh.onrender.com/ask", json={"prompt": prompt})
        reply = r.json()
        audio_url = reply.get("audio_url")

        response = VoiceResponse()

        if audio_url:
            response.play(f"https://render-vps-ypjh.onrender.com{audio_url}")
        else:
            response.say("Hi! How can I help you?")

        # Gather speech from customer
        gather = response.gather(
            input="speech",
            action="/twilio-process",
            method="POST",
            timeout=5,
            speech_timeout="auto"
        )
        gather.say("I'm listening.")

        return Response(str(response), mimetype="application/xml")

    except Exception as e:
        print("Error in /customer-answered:", e)
        response = VoiceResponse()
        response.say("Something went wrong.")
        return Response(str(response), mimetype="application/xml")


# === 3. Handle customer's speech and loop back
@app.route("/twilio-process", methods=["POST"])
def twilio_process():
    speech_input = request.form.get("SpeechResult", "")
    print(f"🗣️ Customer said: {speech_input}")

    response = VoiceResponse()

    if not speech_input:
        response.say("Sorry, I didn't catch that.")
        response.redirect("/customer-answered")
        return Response(str(response), mimetype="application/xml")

    try:
        # Send to GPT + ElevenLabs
        r = requests.post("https://render-vps-ypjh.onrender.com/ask", json={"prompt": speech_input})
        reply = r.json()
        audio_url = reply.get("audio_url")

        if audio_url:
            response.play(f"https://render-vps-ypjh.onrender.com{audio_url}")
        else:
            response.say("I don't have a response right now.")

        # Gather again (loop)
        gather = response.gather(
            input="speech",
            action="/twilio-process",
            method="POST",
            timeout=5,
            speech_timeout="auto"
        )
        gather.say("Go ahead, I'm listening.")

        return Response(str(response), mimetype="application/xml")

    except Exception as e:
        print("Error in /twilio-process:", e)
        response.say("Something went wrong.")
        return Response(str(response), mimetype="application/xml")


# === Run App ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
