from datetime import datetime
from dotenv import load_dotenv
import os
import random
import requests
import sqlite3


load_dotenv()

RESY_PASSWORD = os.getenv('RESY_PASSWORD')
CONCIERGE_CREDIT_CARD_NUMBER = os.getenv('CONCIERGE_CREDIT_CARD_NUMBER')
API_KEY = os.getenv('API_KEY')
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
CONCIERGE_CREDIT_CARD_CVC = os.getenv('CONCIERGE_CREDIT_CARD_CVC')
CONCIERGE_CREDIT_CARD_EXP_YEAR = os.getenv('CONCIERGE_CREDIT_CARD_EXP_YEAR')
CONCIERGE_CREDIT_CARD_EXP_MONTH = os.getenv('CONCIERGE_CREDIT_CARD_EXP_MONTH')
CONCIERGE_CREDIT_CARD_ZIP_CODE = os.getenv('CONCIERGE_CREDIT_CARD_ZIP_CODE')



RESTAURANT_AVAILABILITY_URL = 'https://api.resy.com/4/find'
RESTAURANT_RESERVATION_DETAILS_URL = 'https://api.resy.com/3/details'
RESTAURANT_BOOKING_URL = 'https://api.resy.com/3/book'
RESTAURANT_CONCIERGE_BOOKING_URL = 'https://api.resy.com/3/concierge/book'
USER_AUTHENTICATION_URL = 'https://api.resy.com/3/auth/password'
CONCIERGE_STRIPE_URL = 'https://api.resy.com/3/concierge/stripe/setup_intent'


class WrestyGrabber(object):

  def __init__(self, venue_id, email):
    self.venue_id = venue_id
    self.email = email
    # will need to generalize both api keys for anyone
    self.api_key = API_KEY
    # only used for concierge
    self.stripe_api_key = STRIPE_API_KEY
    self.restaurant_name = None
    self.auth_token = None
    self.first_name = None
    self.last_name = None

  def _pull_user_creds(self):
    conn = sqlite3.connect('wresty.db')
    cur = conn.cursor()
    res = cur.execute(f"SELECT password FROM users where email='{self.email}'")
    resy_password = res.fetchone()[0]
    cur.close()
    conn.close()

    return resy_password

  def _authenticate(self):
    r = requests.post(
        USER_AUTHENTICATION_URL,
        headers = self._get_headers(content_type='application/x-www-form-urlencoded'),
        data = {
          'email': self.email,
          'password': RESY_PASSWORD
          # 'password': self._pull_user_creds(),
        }
      )

    res = r.json()

    self.auth_token = res['token']
    self.first_name = res['first_name']
    self.last_name = res['last_name']

  def search_and_book_reservation(self, date, party_size, start_time=None, end_time=None):
    self._authenticate()
    availabilities = self.get_restaurant_availabilities(date, party_size, start_time, end_time)
    if availabilities:
      self.book_reservation(availabilities, date, party_size)
    else:
      print('No reservations that fit the criteria for you :/')

  def continuously_try_to_book(self, date, party_size, start_time=None, end_time=None, use_concierge=False):
    # save down auth token
    self._authenticate()
    reservations_available = False
    count = 0
    while not reservations_available and count < 1000:
      print(count)
      print(datetime.now())
      availabilities = self.get_restaurant_availabilities(
        date, party_size, start_time, end_time
      )
      if availabilities:
        self.book_reservation(availabilities, date, party_size, use_concierge)
        print(datetime.now())
        reservations_available = True
      else:
        count += 1

  def _get_headers(self, content_type='application/json'):
    return {
      'authority': 'api.resy.com',
      'accept': 'application/json, text/plain, */*',
      'accept-language': 'en-US,en;q=0.9',
      'authorization': f'ResyAPI api_key="{self.api_key}"',
      'content-type': content_type,
      'x-origin': 'https://resy.com',
      'x-resy-auth-token': self.auth_token,
      'x-resy-universal-auth': self.auth_token
    }

  def _get_reservation_booking_post_data(self, res, use_concierge, stripe_payment_method):
    post_data = {
      'book_token': res['book_token']['value'],
      'source_id': 'resy.com-venue-details',
    }

    default_payment_method = next(payment for payment in res['user']['payment_methods'] if payment['is_default'])

    if use_concierge:
      rand_num = random.randint(1000000,9999999)
      rand_email = f'+{rand_num}@'.join(self.email.split("@"))
      rand_phone_number = f'+1800{rand_num}'

      post_data['struct_guest'] = f'{{"em_address":"{rand_email}","first_name":"{self.first_name}","last_name":"{self.last_name}","mobile_number":"{rand_phone_number}"}}'
      post_data['struct_payment_method'] = f'{{"nonce":"{stripe_payment_method}"}}'
    else:
      post_data['struct_payment_method'] = f'{{"id":{default_payment_method["id"]}}}'

    return post_data


  def _authenticate_for_concierge_reservation(self):
    r = requests.post(
        CONCIERGE_STRIPE_URL,
        headers=self._get_headers(content_type='application/x-www-form-urlencoded'),
        data={'venue_id': self.venue_id}
      )

    stripe_res = r.json()
    client_secret = stripe_res.get('client_secret').get('client_secret')
    stripe_account_id = stripe_res.get('client_secret').get('stripe_account_id')

    r = requests.get(
        f'https://api.stripe.com/v1/elements/sessions',
        headers = {
          'authority': 'api.stripe.com',
          'accept': 'application/json',
          'accept-language': 'en-US,en;q=0.9',
          'content-type': 'application/x-www-form-urlencoded',
        },
        params = {
          # my stripe api key. would need to generalize for others who have concierge
          'key': self.stripe_api_key,
          '_stripe_account': stripe_account_id,
          'type': 'setup_intent',
          'locale':'en-US',
          'client_secret': client_secret,
          'expand[0]': 'payment_method_preference.setup_intent.payment_method'
        }
    )

    res = r.json()

    intent_id = res['payment_method_preference']['setup_intent']['id']

    headers = {
      'authority': 'api.stripe.com',
      'accept': 'application/json',
      'accept-language': 'en-US,en;q=0.9',
      'content-type': 'application/x-www-form-urlencoded',
    }

    data = f'payment_method_data[type]=card&payment_method_data[card][number]={CONCIERGE_CREDIT_CARD_NUMBER}&payment_method_data[card][cvc]={CONCIERGE_CREDIT_CARD_CVC}&payment_method_data[card][exp_year]={CONCIERGE_CREDIT_CARD_EXP_YEAR}&payment_method_data[card][exp_month]={CONCIERGE_CREDIT_CARD_EXP_MONTH}&payment_method_data[billing_details][address][postal_code]={CONCIERGE_CREDIT_CARD_ZIP_CODE}&payment_method_data[billing_details][address][country]=US&payment_method_data[pasted_fields]=number&payment_method_data[payment_user_agent]=stripe.js%2F20e004c1e5%3B+stripe-js-v3%2F20e004c1e5%3B+payment-element&payment_method_data[time_on_page]=71503&payment_method_data[guid]=f2e84005-2c3f-4e66-a600-7e64d26b799ce5d780&payment_method_data[muid]=bcf86acb-0f82-4814-bb02-c49687669c82fdfa96&payment_method_data[sid]=4fa22894-2551-451f-9143-6d071d7a7ffb8f91f0&expected_payment_method_type=card&use_stripe_sdk=true&key={self.stripe_api_key}&_stripe_account={stripe_account_id}&client_secret={client_secret}'

    r = requests.post(
        f'https://api.stripe.com/v1/setup_intents/{intent_id}/confirm',
        headers=headers,
        data=data
    )

    res = r.json()

    return res['payment_method']


  def book_reservation(self, availabilities, date, party_size, use_concierge):
    # for each reservation slot, attempt to finalize the booking
    for availability in availabilities:
      print(f'Attempting to book {availability["date"]["start"]} reservation')

      # bring up reservation details page
      r = requests.post(
        RESTAURANT_RESERVATION_DETAILS_URL,
        headers = self._get_headers(),
        json = {
          'commit': 1,
          'config_id': availability['config']['token'],
          'day': date,
          'party_size': party_size,
        }
      )

      details_res = r.json()

      if use_concierge:
        stripe_payment_method = self._authenticate_for_concierge_reservation()
      else:
        stripe_payment_method = None
      # make the booking
      r = requests.post(
        RESTAURANT_CONCIERGE_BOOKING_URL if use_concierge else RESTAURANT_BOOKING_URL,
        headers=self._get_headers(content_type='application/x-www-form-urlencoded'),
        data=self._get_reservation_booking_post_data(details_res, use_concierge, stripe_payment_method)
      )
      try:
        res = r.json()
      except Exception as e:
        print(f'An error occurred trying to book the reservation: {e}')
        print(f'return from api call: {r}')
        raise e

      if res.get('reservation_id') or res.get('concierge_resy_token'):
        print(f'Congratulations! Booked a reservation at {self.restaurant_name} for {party_size} people on {availability["date"]["start"]}')
        return
    print("Sorry, we weren't quick enough to snag a reservation :/")


  def get_restaurant_availabilities(self, date, party_size, start_time=None, end_time=None):
    """
    Pulls all available reservations slots for the specified restaurant, party size, date, and time windows
    """

    try:
      r = requests.get(
        RESTAURANT_AVAILABILITY_URL,
        headers = self._get_headers(),
        params = {
          'lat': '0',
          'long': '0',
          'day': date,
          'party_size': party_size,
          'venue_id': self.venue_id,
        }
      )

      res = r.json()
    except Exception as e:
      print(e)

    desired_availabilities = res.get('results').get('venues', [])[0].get('slots')
    self.restaurant_name = res.get('results').get('venues', [])[0].get('venue').get('name')

    if start_time and end_time:
      start_datetime = datetime.strptime(f'{date} {start_time}', '%Y-%m-%d %H:%M')
      end_datetime = datetime.strptime(f'{date} {end_time}', '%Y-%m-%d %H:%M')

      # filter all availabities to only get those in desired time window
      desired_availabilities = [avail for avail in desired_availabilities if datetime.strptime(avail['date']['start'], '%Y-%m-%d %H:%M:%S') >= start_datetime and datetime.strptime(avail['date']['start'], '%Y-%m-%d %H:%M:%S') <= end_datetime]

    print(f'Found {len(desired_availabilities)} available reservation slots.')

    return desired_availabilities
