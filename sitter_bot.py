import datetime
from multiprocessing import Process
import os
import time
from typing import Tuple, Dict

import parsedatetime as pdt
import pickle

from flask import request, Flask
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

twilio_client = TwilioClient(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))

MY_CELL = os.getenv('MY_CELL')
BOOKER_NUM = os.getenv('MY_TWILIO_NUM')
COUNTRY_CODE = f'+{os.getenv("TWILIO_COUNTRY_CODE")}'
TIMEOUT_MINUTES = 120

help_add = 'You can add a sitter by giving me their first name and 10-digit phone number'
help_text = help_add + ', or book a sitter by ' \
                       'specifying a date and time.  You can also remove a sitter from the list ' \
                       'with "delete" or "remove" and then their first name.'

app = Flask(__name__)
app.config.from_object(__name__)

cal = pdt.Calendar()


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
                start_time, end_time = request_booking(body)
            except ValueError:
                response = 'Please specify an end time (e.g. "tomorrow 5pm to 10pm").'
            else:
                booking_string = make_booking_string(start_time, end_time)
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

    if body not in ['yes', 'no', 'n', 'y'] and not body.isnumeric():
        return f'Hm, I\'m not sure what you meant, {sitter_name.title()}. Please write "yes", "no", ' \
               f'or a number (if there are any pending bookings).'

    action = None

    if not body.isnumeric():
        action = 'accept' if body in ['yes', 'y'] else 'decline'

    if len(sitter_offers) == 0:
        return f'Sorry, {sitter_name.title()}, it looks like either that gig ' \
               f'is already booked or there aren\'t any pending gigs.'

    elif len(sitter_offers) == 1:
        offer = sitter_offers[0]

    else:
        sitter_offers_string = ", ".join([f'{idx + 1}) {make_booking_string(*sitter_offer)}'
                                          for idx, sitter_offer in enumerate(sitter_offers)])

        if body.isnumeric():
            try:
                offer = sitter_offers[int(body) - 1]
            except IndexError:
                action = sitter['next action']
                return f'Sorry, which booking did you want to {action}? {sitter_offers_string}'
        else:
            sitter['next action'] = action
            persist_sitters()
            return f'Sorry, which booking did you want to {action}? {sitter_offers_string}'

    try:
        action = action or sitter.pop('next action')
    except KeyError:
        raise KeyError(f'no next action, and sitter_offers is {sitter_offers}, so offer is {offer}.')
    booking_string = make_booking_string(*offer)

    if action == 'accept':

        if not bookings.get(offer):
            return f'Sorry, {sitter_name.title()}, it looks like {booking_string} is already booked.'

        if any(bookings[offer]['offered'][sitter_] == 'yes'
               for sitter_ in bookings[offer]['offered'].keys()):
            if bookings[offer]['offered'][sitter_name] == 'yes':
                return f'You already accepted {booking_string}, {sitter_name.title()}!'
            return f'Sorry, {sitter_name.title()}, it looks like {booking_string} is already booked.'

        bookings[offer]['offered'][sitter_name] = 'yes'
        persist_bookings()
        update_client(f'{sitter_name.title()} agreed to babysit on {booking_string}!')
        return f'Awesome, {sitter_name.title()}!  See you on {booking_string}.'

    else:
        if bookings[offer]['offered'][sitter_name] == 'yes':
            return f'You already accepted {booking_string}, {sitter_name.title()}!'

        bookings[offer]['offered'][sitter_name] = 'no'
        persist_bookings()
        return f'Okay, no problem, {sitter_name.title()}!  Next time.'


def make_booking_string(start_time: datetime.datetime, end_time: datetime.time) -> str:
    start_time_and_date_string = start_time.strftime('%-m/%-d from %-I:%M%p')
    end_time_string = end_time.strftime('%-I:%M%p')
    return f'{start_time_and_date_string} to {end_time_string}'


def book_forever():
    while True:

        sitters_, bookings_ = load_from_pickle('sitters'), load_from_pickle('bookings')

        if bookings_:

            bookings_keys_to_delete = []

            for booking_start_and_end, offered_dict in bookings_.items():

                booking = bookings_[booking_start_and_end]
                offers = booking['offered']

                if any(v == 'yes' for k, v in offers.items()):
                    continue

                sitter_to_offer_name = None
                booking_string = make_booking_string(*booking_start_and_end)

                if len(offers) == 0:
                    first_sitter_name = list(sitters_)[0]
                    sitter_to_offer_name = first_sitter_name
                else:
                    last_offer_was_minutes_ago = 0
                    offers_without_a_no = {k: v for k, v in offers.items() if v != 'no'}
                    if len(offers_without_a_no) > 0:
                        last_offer: datetime.datetime = max(offers_without_a_no.values())
                        last_offer_was_minutes_ago \
                            = (datetime.datetime.now() - last_offer).total_seconds() / 60

                    if len(offers_without_a_no) == 0 or last_offer_was_minutes_ago > 1:
                    # if len(offers_without_a_no) == 0 or last_offer_was_minutes_ago > 60:

                        # if len(sitters_) == len(offers):
                        #     bookings_keys_to_delete.append(booking_start_and_end)
                        #     update_client(
                        #         f'No babysitters are available for {booking_string}! Deleting request.')

                        # else:
                        for sitter in sitters_:
                            if sitter not in offers:
                                sitter_to_offer_name = sitter
                                break

                if sitter_to_offer_name is not None:
                    sitter_to_offer = sitters_[sitter_to_offer_name]
                    offer_booking(sitter_to_offer, booking_string)
                    offers[sitter_to_offer_name] = datetime.datetime.now()
                    update_client(
                        f'Okay, I offered {booking_string} to {sitter_to_offer_name.title()}.')

            if len(bookings_keys_to_delete) > 0:
                for k in bookings_keys_to_delete:
                    del bookings_[k]

            persist_bookings(bookings_)

        # time.sleep(60)
        time.sleep(5)


def offer_booking(sitter_dict: dict, booking_string: str) -> None:
    message = f'{sitter_dict["name"].title()}, are you available to babysit on {booking_string}?'
    twilio_client.api.account.messages.create(to=sitter_dict['num'],
                                              from_=BOOKER_NUM,
                                              body=message)


def update_client(string: str) -> None:
    twilio_client.api.account.messages.create(to=MY_CELL, from_=BOOKER_NUM, body=string)


def has_phone_num(string):
    return len([char for char in string if char.isnumeric()]) == 10


def request_booking(body: str) -> Tuple[datetime.datetime, datetime.time]:
    session_start, session_end = parse_booking_request(body)
    global bookings
    bookings = load_from_pickle('bookings')
    bookings[(session_start, session_end)] = {'offered': dict()}
    persist_bookings()
    return session_start, session_end


def parse_booking_request(body: str) -> Tuple[datetime.datetime, datetime.time]:
    start_string, end_string = body.split(' to ')
    session_start = cal.parseDT(start_string)[0]
    session_end_time = datetime.time(cal.parse(end_string)[0].tm_hour)
    return session_start, session_end_time


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
    p = Process(target=book_forever)
    p.start()
    app.run(debug=True, port=8000)
    p.join()
