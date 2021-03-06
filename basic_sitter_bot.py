import os
from typing import Tuple

from flask import Flask, request
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

app = Flask(__name__)
app.config.from_object(__name__)

sitters = {}

@app.route('/bot', methods=['POST'])
def bot():
    from_ = request.values.get('From')
    body = request.values.get('Body').lower()
    response = 'I wasn\'t sure what to do with your input. '

    if has_phone_num(body):

        try:
            sitter_name, sitter_num = add_sitter(body)
        except (AssertionError, ValueError):
            response = 'Sorry, did you mean to add a sitter?  Please try again.'
        else:
            response = f'Okay, I added {sitter_name.title()} to sitters, with phone # {sitter_num}.  '
            print(sitters)

    resp = MessagingResponse()
    resp.message(response)
    return str(resp)


def has_phone_num(string):
    return len([char for char in string if char.isnumeric()]) == 10


def add_sitter(body: str) -> Tuple[str, str]:
    name, *num_parts = body.split(' ')

    num_only = ''.join(char
                       for num in num_parts
                       for char in num if char.isnumeric())

    lowercase_name = name.lower()
    sitter = sitters.get(lowercase_name)

    assert len(num_only) == 10

    phone_number = f'+1{num_only}'
    sitters[lowercase_name] = {'num':  phone_number,
                               'name': lowercase_name}

    return name, phone_number


if __name__ == '__main__':
    app.run(debug=True, port=8000, use_reloader=False)

