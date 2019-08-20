import datetime
from multiprocessing import Process
import os
from pprint import pprint
import time
from typing import Tuple, Dict

import parsedatetime as pdt
import pickle

from flask import request, Flask
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

MY_CELL = os.getenv('MY_CELL')
BOT_NUM = os.getenv('MY_TWILIO_NUM')
COUNTRY_CODE = f'+{os.getenv("TWILIO_COUNTRY_CODE")}'
TIMEOUT_MINUTES = 120

help_add = 'You can add a sitter by giving me their first name and 10-digit phone number'
help_text = help_add + ', or book a sitter by ' \
                       'specifying a date and time.  You can also remove a sitter from the list ' \
                       'with "delete" or "remove" and then their first name.'

app = Flask(__name__)
app.config.from_object(__name__)

cal = pdt.Calendar()


class TheresAlreadyAnActiveBooking(Exception):
    pass


def load_from_pickle(var_name: str) -> dict:
    payload = {}
    if os.path.exists(f'{var_name}.p'):
        payload = pickle.load(open(f'{var_name}.p', 'rb'))
    return payload


sitters, bookings = load_from_pickle('sitters'), load_from_pickle('bookings')
sitters_num_name_lookup = {v['num']: k for k, v in sitters.items()}


@app.route('/bot', methods=['POST'])
def bot() -> str:
    from_ = request.values.get('From')
    body = request.values.get('Body').lower()

    resp = MessagingResponse()
    response = ''

    if from_ == MY_CELL:

        if has_phone_num(body):

            try:
                sitter_name, sitter_num = add_sitter(body)
            except (AssertionError, ValueError):
                response = 'Sorry, did you mean to add a sitter?  Please try again.'
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
                start_datetime, end_time = request_booking(body)
            except ValueError:
                response = 'Please specify an end time (e.g. "tomorrow 5pm to 10pm").'
            except TheresAlreadyAnActiveBooking:
                response = 'Please wait until the current booking is either booked or expires.'
            else:
                booking_string = make_booking_string(start_datetime, end_time)
                response = f'Okay, I will reach out to the sitters about sitting on {booking_string}.'

        if response is None:
            response = 'I wasn\'t sure what to do with your input. ' + help_text

    else:

        sitter_name = sitters_num_name_lookup.get(from_)
        if sitter_name is not None:
            response = accept_or_decline(sitter_name, body)

    resp.message(response)

    return str(resp)


def accept_or_decline(sitter_name: str, body: str) -> str:
    body = body.strip()

    global bookings
    global sitters

    bookings, sitters = load_from_pickle('bookings'), load_from_pickle('sitters')
    sitter = sitters[sitter_name]

    sitter_offers = [k for k, v in bookings.items()
                     if sitter_name in v['offered']
                     if v['offered'][sitter_name] not in ['yes', 'no']]

    if len(sitter_offers) == 0:
        update_client(f'there\'s more than one booking on offer, so I\'m confused!')
        return f'Sorry, {sitter_name.title()}, there are no pending gigs.'

    elif len(sitter_offers) > 1:
        return f'I\'m not sure which offer you\'re responding to!'

    offer = sitter_offers[0]
    booking = bookings[offer]

    if body not in ['yes', 'no', 'n', 'y']:
        return f'Hm, I\'m not sure what you meant, {sitter_name.title()}. Please write "yes" or "no".'

    if body in ['yes', 'y']:

        booking_string = make_booking_string(*offer)

        if any(booking['offered'][sitter_] == 'yes'
               for sitter_ in booking['offered'].keys()):
            return f'Sorry, {sitter_name.title()}, it looks like {booking_string} is already booked.'

        booking['offered'][sitter_name] = 'yes'
        persist_bookings()
        update_client(f'{sitter_name.title()} agreed to babysit on {booking_string}!')
        return f'Awesome, {sitter_name.title()}!  See you on {booking_string}.'

    booking['offered'][sitter_name] = 'no'
    persist_bookings()
    return f'Okay, no problem, {sitter_name.title()}!  Next time.'


def make_booking_string(start_datetime: datetime.datetime, end_time: datetime.time) -> str:
    start_time_and_date_string = start_datetime.strftime('%-m/%-d from %-I:%M%p')
    end_time_string = end_time.strftime('%-I:%M%p')
    return f'{start_time_and_date_string} to {end_time_string}'


def book_forever():
    while True:

        sitters_, bookings_ = load_from_pickle('sitters'), load_from_pickle('bookings')

        if sitters_ and bookings_:

            for booking_start_and_end, offered_dict in bookings_.items():

                booking = bookings_[booking_start_and_end]
                offers = booking['offered']

                if any(v == 'yes' for k, v in offers.items()):
                    continue

                if len(sitters_) == len(offers):
                    continue

                booking_string = make_booking_string(*booking_start_and_end)

                for sitter_name, sitter_dict in sitters_.items():
                    if sitter_name not in offers:
                        offer_booking(sitter_dict, booking_string)
                        offers[sitter_name] = datetime.datetime.now()
                        update_client(
                            f'Okay, I offered {booking_string} to {sitter_name.title()}.')

                pprint(bookings_)

            persist_bookings(bookings_)

        # time.sleep(60)
        time.sleep(5)


def offer_booking(sitter_dict: dict, booking_string: str) -> None:
    message = f'{sitter_dict["name"].title()}, are you available to babysit on {booking_string}?'
    twilio_client.api.account.messages.create(to=sitter_dict['num'],
                                              from_=BOT_NUM,
                                              body=message)

def update_client(string: str) -> None:
    twilio_client.api.account.messages.create(to=MY_CELL, from_=BOT_NUM, body=string)


def has_phone_num(string):
    return len([char for char in string if char.isnumeric()]) == 10


def request_booking(body: str) -> Tuple[datetime.datetime, datetime.time]:
    session_start_datetime, session_end_time = parse_booking_request(body)
    global bookings
    bookings = load_from_pickle('bookings')
    if bookings:
        raise TheresAlreadyAnActiveBooking
    bookings[(session_start_datetime, session_end_time)] = {'offered': dict()}
    persist_bookings()
    return session_start_datetime, session_end_time


def parse_booking_request(body: str) -> Tuple[datetime.datetime, datetime.time]:
    start_string, end_string = body.split(' to ')
    session_start_datetime = cal.parseDT(start_string)[0]
    session_end_time = datetime.time(cal.parse(end_string)[0].tm_hour)
    return session_start_datetime, session_end_time


def add_sitter(body: str) -> Tuple[str, str]:
    name, *num_parts = body.split(' ')

    num_only = ''.join(char
                       for num in num_parts
                       for char in num if char.isnumeric())

    lowercase_name = name.lower()

    assert len(num_only) == 10

    phone_number = f'{COUNTRY_CODE}{num_only}'
    sitters[lowercase_name] = {'num': phone_number,
                               'name': lowercase_name}

    persist_sitters()
    return name, phone_number


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


def persist_bookings(bookings_: dict = None):
    pickle.dump(bookings_ if bookings_ is not None else bookings, open('bookings.p', 'wb'))


if __name__ == '__main__':
    update_client('Hi, this is Babysitter Bot, on the job!  Send me a date with time range and '
                  'I\'ll try to book one of our sitters!')
    if not sitters:
        update_client('Please add at least one babysitter.')
    p = Process(target=book_forever)
    p.start()
    app.run(debug=True, port=8000, use_reloader=False)
    p.join()
