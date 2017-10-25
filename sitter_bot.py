import datetime
import os
from typing import Optional, Tuple

import pickle
from flask import request, Flask
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

MY_CELL = os.getenv('MY_CELL')
BOOKER_NUM = os.getenv('MY_TWILIO_NUM')
COUNTRY_CODE = f'+{os.getenv("TWILIO_COUNTRY_CODE")}'
TIMEOUT_MINUTES = 120

sitters = {}
if os.path.exists('sitters.p'):
    sitters = pickle.load(open('sitters.p', 'rb'))

bookings = {}
if os.path.exists('bookings.p'):
    bookings = pickle.load(open('bookings.p', 'rb'))

help_add = 'You can add a sitter by giving me their first name and 10-digit phone number'
help_text = help_add + ', or book a sitter by ' \
            'specifying a date and time.  You can also remove a sitter from the list ' \
            'with "delete" or "remove" and then their first name.'

app = Flask(__name__)
app.config.from_object(__name__)


class AlreadyExists(Exception):
    pass


class NoneAvailable(Exception):
    pass


def say_hi_ask_for_sitters():
    message = "Hey, can you tell me your sitters' info one at a time? " \
              "First name then phone num. By the way, if you need help, type 'halp' at any time"
    twilio_client.api.account.messages.create(to=MY_CELL, from_=BOOKER_NUM, body=message)


@app.route('/bot', methods=['POST'])
def bot() -> str:
    from_ = request.values.get('From')
    body = request.values.get('Body').lower()

    resp = MessagingResponse()
    response = None

    if not from_ == MY_CELL:
        return str(resp.message(''))

    if 'halp' in body:
        if not sitters:
            response = f'You don\'t have any sitters yet. {help_add}.'
        else:
            sitter_list = 'Your sitters are ' + ' and '.join(
                f'{sitter_name.title()}' for sitter_name in sitters) + '.'
            response = f'{sitter_list} {help_text}'

    elif has_phone_num(body):

        try:
            sitter_name, sitter_num = add_sitter(body)
        except (AssertionError, ValueError):
            response = 'Sorry, did you mean to add a sitter?  Please try again.'
        except AlreadyExists as e:
            sitter_name = e.args[0]
            response = f'{sitter_name.title()} already exists!'
        else:
            response = f'Okay, I added {sitter_name.title()} to sitters, with phone # {sitter_num}.  '

    elif any(remove_word in body for remove_word in ['remove', 'delete']):

        try:
            sitter_name = remove_sitter(body)
        except KeyError:
            response = 'No such sitter. Please write "delete [sitter\'s first name]."'
        else:
            response = f'Okay, I removed {sitter_name.title()} from the sitters.'

    else:
        try:
            book_sitter(body)
        except (AssertionError, ValueError):
            response = 'Sorry, did you mean to book a sitter?  Please try again.'

    if response is None:
        response = 'I wasn\'t sure what to do with your input. ' + help_text

    resp.message(response)

    return str(resp)


def has_phone_num(string):
    return len([char for char in string if char.isnumeric()]) == 10


def syndicate_and_book(session_start: datetime.datetime, session_end: datetime.datetime) -> Optional[str]:
    # blast out to all sitters
    # give it to the first 'yes'
    # handle late 'yeses' and all 'noes'
    # wait until everyone says no or timeout_minutes runs out
    pass


def book_sitter(body: str) -> Optional[str]:
    session_start, session_end = parse_sitter_request(body)
    syndicate_and_book(session_start, session_end)


def add_sitter(body: str) -> Tuple[str, str]:
    name, *num_parts = body.split(' ')

    num_only = ''.join(char
                       for num in num_parts
                       for char in num if char.isnumeric())

    lowercase_name = name.lower()
    sitter = sitters.get(lowercase_name)

    if sitter is not None:
        raise AlreadyExists(lowercase_name)

    assert len(num_only) == 10

    sitters[lowercase_name] = f'{COUNTRY_CODE}num_only'
    persist_sitters()
    return name, sitters[lowercase_name]


def remove_sitter(body: str) -> str:
    sitter_first_name = body.split(' ')[1]
    sitter = sitters.get(sitter_first_name)
    if sitter is None:
        raise KeyError
    del sitters[sitter_first_name]
    persist_sitters()
    return sitter_first_name


def persist_sitters():
    pickle.dump(sitters, open('sitters.p', 'wb'))


if __name__ == '__main__':
    if not sitters:
        say_hi_ask_for_sitters()
    app.run(debug=True, port=4567)
