import os

import hug
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse


twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

my_cell = os.getenv('MY_CELL')
booker_num = os.getenv('MY_TWILIO_NUM')
timeout_minutes = 120
sitters = {}


def say_hi_ask_for_sitters():
    message = "Hey, can you tell me your sitters' info one at a time?"
    twilio_client.api.account.messages.create(to=my_cell, from_=my_twilio_num, body=message)


@hug.post('/')
def booker(incoming_message):
    from_num = incoming_message['From']
    print(vars(incoming_message))

    if from_num not in [list(sitters.values()) += [my_cell]]:
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


def syndicate_and_book(session_start, session_end):
    # blast out to all sitters
    # give it to the first 'yes'
    # handle late 'yeses' and all 'noes'
    # wait until everyone says no or timeout_minutes runs out


def book_sitter(in_message):
    session_start, session_end = parse_sitter_request(in_message)
    syndicate_and_book(session_start, session_end)


def add_sitter(in_message):
    try:
        name, num = parse_sitter_info(in_message)
    except CouldntParse:
        raise
    else:
        sitters[name] = num
