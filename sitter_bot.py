import datetime
import os
import re
from typing import Optional

from flask import request, Flask
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse


twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

my_cell = os.getenv('MY_CELL')
booker_num = os.getenv('MY_TWILIO_NUM')
timeout_minutes = 120
sitters = {}

app = Flask(__name__)
app.config.from_object(__name__)


class CouldntParse(Exception):
    pass


class NoneAvailable(Exception):
    pass


def say_hi_ask_for_sitters():
    message = "Hey, can you tell me your sitters' info one at a time?"
    twilio_client.api.account.messages.create(to=my_cell, from_=booker_num, body=message)


@app.route('/booker', methods=['POST'])
def booker() -> str:
    from_ = request.values.get('From')
    body = request.values.get('Body')
    message = None

    if from_ == my_cell:
        # from me
        if has_phone_num(body):
            try:
                add_sitter(body)
            except CouldntParse:
                message = 'Sorry, did you mean to add a sitter?  Please try again.'
        else:
            try:
                book_sitter(body)
            except CouldntParse:
                message = 'Sorry, did you mean to book a sitter?  Please try again.'
            except NoneAvailable:
                message = f'Darn, I wasn\'t able to book a sitter.  I waited {timeout_minutes} minutes.'

    elif from_ in sitter.values():
        if body.strip().lower() == 'yes':

    if message is None:
        message = 'I wasn\'t sure what to do with your input. Try again?'

    resp = MessagingResponse()
    resp.message(message)

    return str(resp)


def has_phone_num(string):
    return bool(re.match('\+[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]', string))


def syndicate_and_book(session_start: datetime.datetime, session_end: datetime.datetime) -> Optional[str]:
    # blast out to all sitters
    # give it to the first 'yes'
    # handle late 'yeses' and all 'noes'
    # wait until everyone says no or timeout_minutes runs out
    pass


def book_sitter(in_message: str) -> Optional[str]:
    session_start, session_end = parse_sitter_request(in_message)
    syndicate_and_book(session_start, session_end)


def add_sitter(in_message: str):
    try:
        name, num = parse_sitter_info(in_message)
    except CouldntParse:
        raise
    else:
        sitters[name] = num


def parse_sitter_info(string):
    pass


def parse_sitter_request(string):
    pass


if __name__ == '__main__':
    say_hi_ask_for_sitters()
    app.run(debug=True, port=8000)
