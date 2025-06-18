from fastapi import FastAPI, Request, UploadFile
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI
import os, csv, io
from fastapi.responses import Response

load_dotenv()

app = FastAPI()

# Load environment variables
openai_client = OpenAI()  # Automatically loads from OPENAI_API_KEY env var
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
twilio_webhook = os.getenv("VOICE_WEBHOOK_URL")
ai_greeting = os.getenv("AI_GREETING", "Hi! How can I help you?")
agent_number = os.getenv("AGENT_PHONE_NUMBER")

twilio_client = Client(twilio_sid, twilio_token)
greeted_callers = set()

@app.api_route("/voice", methods=["POST", "GET"])
async def voice_response(request: Request):
    form = await request.form()
    from_number = form.get("From")
    speech_result = form.get("SpeechResult")

    print("------ Incoming Twilio POST ------")
    for key, value in form.items():
        print(f"{key}: {value}")

    response = VoiceResponse()

    if from_number not in greeted_callers:
        greeted_callers.add(from_number)

        gather = Gather(
            input="speech",
            timeout=5,
            speechTimeout="auto",
            action=twilio_webhook,
            method="POST"
        )
        gather.pause(length=1)  # Prevent speech cutoff
        gather.say(ai_greeting, voice="alice")
        response.append(gather)
        response.redirect(twilio_webhook)
        return Response(content=str(response), media_type="application/xml")

    if not speech_result or not speech_result.strip():
        response.say("Sorry, I didn't catch that. Please try again.", voice="alice")
        response.redirect(twilio_webhook)
        return Response(content=str(response), media_type="application/xml")

    try:
        ai_reply = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": speech_result}]
        )
        reply_text = ai_reply.choices[0].message.content.strip()
        print(f"AI replied: {reply_text}")
    except Exception as e:
        print(f"OpenAI error: {e}")
        reply_text = "Sorry, I'm having trouble understanding right now."

    gather = Gather(
        input="speech",
        timeout=5,
        speechTimeout="auto",
        action=twilio_webhook,
        method="POST"
    )
    gather.pause(length=1)
    gather.say(reply_text, voice="alice")
    response.append(gather)
    response.redirect(twilio_webhook)

    return Response(content=str(response), media_type="application/xml")


@app.post("/call-from-csv/")
async def call_from_csv(file: UploadFile):
    contents = await file.read()
    decoded = contents.decode("utf-8")
    reader = csv.reader(io.StringIO(decoded))

    for row in reader:
        if row:
            number = row[0].strip()
            if number:
                call = twilio_client.calls.create(
                    to=number,
                    from_=twilio_number,
                    url=twilio_webhook
                )
                print(f"Calling {number}, Call SID: {call.sid}")

    return {"message": "Calls initiated"}
