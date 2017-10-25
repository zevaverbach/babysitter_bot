import os

from flask import Flask, request
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

app = Flask(__name__)
app.config.from_object(__name__)

@app.route('/bot', methods=['POST'])
def bot():
    from_ = request.values.get('From')
    body = request.values.get('Body').lower()
    resp = MessagingResponse()
    resp.message(f'ok, you said {body}.')
    return str(resp)

if __name__ == '__main__':
    app.run(debug=True, port=8000)

