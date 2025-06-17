from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
from twilio.rest import Client
from dotenv import load_dotenv
import openai, os, csv, io

load_dotenv()

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
twilio_webhook = os.getenv("TWILIO_WEBHOOK_URL")
ai_greeting = os.getenv("AI_GREETING", "Hi! How can I help you?")
agent_number = os.getenv("AGENT_PHONE_NUMBER")

twilio_client = Client(twilio_sid, twilio_token)
greeting_mode = {}


@app.post("/voice", response_class=PlainTextResponse)
async def voice_response(request: Request):
    form = await request.form()
    from_number = form.get("From")
    speech_result = form.get("SpeechResult", "")

    response = VoiceResponse()

    if from_number not in greeting_mode:
        greeting_mode[from_number] = True
        gather = Gather(input="speech", action="/voice", timeout=3, speechTimeout="auto")
        gather.say(ai_greeting, voice="alice")
        response.append(gather)
        return str(response)

    # check if user is interested
    interested_keywords = ["yes", "interested", "sure", "okay", "yeah", "want", "go ahead"]

    if any(word in speech_result.lower() for word in interested_keywords):
        response.say("Great! Connecting you to a live agent now.", voice="alice")
        response.dial(agent_number)
        return str(response)

    # otherwise continue conversation with AI
    ai_reply = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": speech_result}]
    )
    reply_text = ai_reply.choices[0].message.content

    gather = Gather(input="speech", action="/voice", timeout=3, speechTimeout="auto")
    gather.say(reply_text, voice="alice")
    response.append(gather)
    return str(response)


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
