import datetime
import os
from typing import Optional

import hug
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse


twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

my_cell = os.getenv('MY_CELL')
booker_num = os.getenv('MY_TWILIO_NUM')
timeout_minutes = 120
sitters = {}


class CouldntParse(Exception):
    pass


class NoneAvailable(Exception):
    pass


def say_hi_ask_for_sitters():
    message = "Hey, can you tell me your sitters' info one at a time?"
    twilio_client.api.account.messages.create(to=my_cell, from_=booker_num, body=message)


@hug.post('/')
def booker(incoming_message: str) -> str:
    from_num = incoming_message['From']
    print(vars(incoming_message))

    if from_num not in list(sitters.values()) + [my_cell]:
        # unknown number
        return

    in_message = incoming_message['Body']

    if from_num == my_cell:
        if has_phone_num(in_message):
            try:
                add_sitter(in_message)
            except CouldntParse:
                response = 'Sorry, did you mean to add a sitter?  Please try again.'
        else:
            try:
                book_sitter(in_message)
            except CouldntParse:
                response = 'Sorry, did you mean to book a sitter?  Please try again.'
            except NoneAvailable:
                response = f'Darn, I wasn\'t able to book a sitter.  I waited {timeout_minutes} minutes.'


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


if __name__ == '__main__':
    say_hi_ask_for_sitters()
    hug.API(__name__).http.serve()
