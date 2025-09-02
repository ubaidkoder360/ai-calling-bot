from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import Response, JSONResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI
import os, csv, io

load_dotenv()
app = FastAPI()

# --- Load Config ---
openai_client = OpenAI()
twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
twilio_webhook = os.getenv("VOICE_WEBHOOK_URL")
ai_greeting = os.getenv("AI_GREETING", "Hi! this is Jason calling from Biopharma Informatics.")
agent_number = os.getenv("AGENT_PHONE_NUMBER")

twilio_client = Client(twilio_sid, twilio_token)


# -----------------------------
# Voice Webhook
# -----------------------------
@app.api_route("/voice", methods=["POST", "GET"])
async def voice_response(request: Request):
    form = await request.form()
    from_number = form.get("From")
    speech_result = form.get("SpeechResult")

    print("\n------ Incoming Twilio Webhook ------")
    for key, value in form.items():
        print(f"{key}: {value}")
    print(f"DEBUG Caller: {from_number}")
    print(f"DEBUG SpeechResult: {speech_result}")

    response = VoiceResponse()

    # First time: no speech yet → greet and gather
    if not speech_result:
        print("DEBUG: Sending initial greeting...")

        gather = Gather(
            input="speech",
            timeout=3,
            speech_timeout="auto",
            action=twilio_webhook,
            method="POST",
            language="en-US"
        )

        gather.say(ai_greeting, voice="bob")
        gather.pause(length=1)
        gather.say("How are you doing today?", voice="bob")

        response.append(gather)

        # if no speech → repeat
        response.redirect(twilio_webhook)
        return Response(content=str(response), media_type="application/xml")

    # If Twilio returned empty speech
    if not speech_result.strip():
        response.say("Sorry, I didn’t catch that. Let’s try again.", voice="bob")
        response.redirect(twilio_webhook)
        return Response(content=str(response), media_type="application/xml")

    # Process input with OpenAI
    try:
        print("DEBUG: Sending speech to OpenAI...")
        ai_reply = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": speech_result}]
        )
        reply_text = ai_reply.choices[0].message.content.strip()
        print(f"DEBUG OpenAI reply: {reply_text}")
    except Exception as e:
        print(f"ERROR OpenAI failed: {e}")
        reply_text = "I’m having trouble understanding. Let me transfer you to a specialist."

    # Respond with AI reply
    response.say(reply_text, voice="bob")
    response.pause(length=1)

    # Transfer to agent
    if agent_number:
        response.say("Please hold while I transfer your call.", voice="bob")
        dial = response.dial(caller_id=twilio_number)
        dial.number(agent_number)
        print(f"DEBUG: Transferring call to {agent_number}")
    else:
        response.say("All our agents are busy. We’ll call you back shortly.", voice="bob")
        print("DEBUG: Agent number not set.")

    return Response(content=str(response), media_type="application/xml")


# -----------------------------
# Call from CSV
# -----------------------------
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


# -----------------------------
# Call single number
# -----------------------------
@app.post("/call-single-number/")
async def call_single_number(payload: dict):
    number = payload.get("number")
    if not number:
        return JSONResponse(status_code=400, content={"error": "Number is required"})

    try:
        call = twilio_client.calls.create(
            to=number,
            from_=twilio_number,
            url=twilio_webhook
        )
        return {"message": f"Calling {number}", "call_sid": call.sid}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
