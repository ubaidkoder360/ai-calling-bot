from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
import openai, os

load_dotenv()
app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY")
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
client = Client(twilio_sid, twilio_token)

@app.post("/voice", response_class=PlainTextResponse)
async def inbound_call(request: Request):
    form = await request.form()
    speech_text = form.get("SpeechResult", "Hello")
    
    # AI response
    ai_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": speech_text}]
    )
    reply = ai_response.choices[0].message.content

    # Respond to Twilio
    response = VoiceResponse()
    gather = Gather(input="speech", action="/voice", timeout=3, speechTimeout="auto")
    gather.say(reply, voice="alice")
    response.append(gather)
    response.pause(length=1)
    response.say("Goodbye.", voice="alice")
    return str(response)

@app.post("/outbound")
def outbound_call(to_number: str = Form(...)):
    call = client.calls.create(
        to=to_number,
        from_=twilio_number,
        url="https://your-ngrok-url.ngrok.io/voice"
    )
    return {"message": "Calling...", "sid": call.sid}
