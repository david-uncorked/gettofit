from rauth import OAuth1Service, OAuth2Service, OAuth2Session
from flask import jsonify, current_app, url_for, request, redirect, session
from oauth import OAuthProvider
import urllib2
import requests
import json
import logging
import pytz 
import urllib
import up_workout_map

from datetime import datetime, timedelta
import calendar

def date_to_nano(ts):
    """
    Takes a datetime object and returns POSIX UTC in nanoseconds
    """
    return calendar.timegm(ts.utctimetuple()) * int(1e9)


def date_to_millis(ts):
    return calendar.timegm(ts.utctimetuple()) * 1000


def is_dst(zonename):
    tz = pytz.timezone(zonename)
    now = pytz.utc.localize(datetime.utcnow())
    return now.astimezone(tz).dst() != timedelta(0)

class JawboneOAuthAdapter(OAuthProvider):
    def __init__(self):
        super(JawboneOAuthAdapter, self).__init__('jawbone')
        self.service = OAuth2Service(
            name='jawbone',
            client_id=self.consumer_id,
            client_secret=self.consumer_secret,
            authorize_url='https://jawbone.com/auth/oauth2/auth',
            access_token_url='https://jawbone.com/auth/oauth2/token',
            base_url='https://jawbone.com/'
        )

    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='basic_read extended_read move_read move_write location_read friends_read mood_read mood_write sleep_read sleep_write meal_read meal_write weight_read weight_write generic_event_read generic_event_write heartrate_read',
            response_type='code',
            redirect_uri=self.get_callback_url())
        )

    def get_user(self, token):
        oauth_session = self.service.get_session(token)
        me = oauth_session.get('nudge/api/v.1.1/users/@me').json()
        return (
            me['data']['xid'],
            me['data']['first'] + " " + me['data']['last']
        )

    def get_callback_url(self):
        return url_for('oauth_jawbone_callback', provider=self.provider_name,
                       _external=True)

    def callback(self):
        if 'code' not in request.args:
            return None, None, None
        oauth_session_data = self.service.get_raw_access_token(
            data={'code': request.args['code'],
              'grant_type': 'authorization_code',
              'client_secret': self.consumer_secret,
              'client_id': self.consumer_id,
              'redirect_uri': self.get_callback_url()}
        )
        oauth_session = oauth_session_data.json()
        return (oauth_session['access_token'], oauth_session['refresh_token'])

    def get_moves(self, token, move_xid=None):
        oauth_session = self.service.get_session(token)
        if move_xid is not None:
            moves = oauth_session.get("nudge/api/v.1.1/moves/" + move_xid).json()
        else:
            moves = oauth_session.get("nudge/api/v.1.1/users/@me/moves").json()
        if moves is None:
           return None
        if not moves.has_key('data'):
           return None
        if not moves['data'].has_key('size'):
           return None
        if not moves['data'].has_key('items'):
           return None

        item_count = moves['data']['size']
        items = moves['data']['items']
        results_dict = dict()

        for x in range(0, item_count):
           hourly_totals = items[x]['details']['hourly_totals']
           tzinfo = items[x]['details']['tzs'][0][1]
           for key, value in hourly_totals.iteritems():
               date_object = datetime.strptime(key, '%Y%m%d%H')
               # logging.info(tzinfo)
               local = pytz.timezone (tzinfo)
               local_dt = local.localize(date_object, is_dst(tzinfo))
               utc_dt = local_dt.astimezone (pytz.utc)
               # logging.info(str(date_to_nano(utc_dt)))
               results_dict[str(date_to_nano(utc_dt))] = value['steps']

        return results_dict

    def get_one_move(self, token, move_xid):
        oauth_session = self.service.get_session(token)
        moves = oauth_session.get("nudge/api/v.1.1/moves/" + move_xid).json()

        if moves is None:
           return None
        if not moves.has_key("data"):
           return None

        items = moves['data']
        results_dict = dict()

        if not items.has_key("details"):
           return None
        if not items['details'].has_key("hourly_totals"):
           return None

        hourly_totals = items['details']['hourly_totals']
        if not moves.has_key("data"):
           return None

        tzinfo = items['details']['tzs'][0][1]
        for key, value in hourly_totals.iteritems():
            date_object = datetime.strptime(key, '%Y%m%d%H')
            local = pytz.timezone (tzinfo)
            local_dt = local.localize(date_object, is_dst(tzinfo))
            utc_dt = local_dt.astimezone (pytz.utc)
            results_dict[str(date_to_nano(utc_dt))] = value['steps']
        return results_dict

    def get_one_workout(self, token, workout_xid):
        oauth_session = self.service.get_session(token)
        workout = oauth_session.get("nudge/api/v.1.1/workouts/" + workout_xid).json()

        if workout is None:
           return None
        if not workout.has_key("data"):
           return None

        info = workout['data']
        results_dict = dict()

        if not info.has_key("details"):
           return None
        if not info['details'].has_key("tz"):
           return None

        tzinfo = info['details']['tz']

        time_created = info["time_created"]
        time_completed = info["time_completed"]
        time_updated = info["time_updated"]
        results_dict['sub_type'] = info["sub_type"]
        results_dict['title'] = info["title"]

        created_object = datetime.fromtimestamp(time_created)
        local = pytz.timezone(tzinfo)
        local_dt = local.localize(created_object, is_dst(tzinfo))
        utc_dt = local_dt.astimezone (pytz.utc)
        results_dict['time_created'] = date_to_millis(created_object)

        completed_object = datetime.fromtimestamp(time_completed)
        local = pytz.timezone(tzinfo)
        local_dt = local.localize(completed_object, is_dst(tzinfo))
        utc_dt = local_dt.astimezone(pytz.utc)
        results_dict['time_completed'] = date_to_millis(completed_object)

        updated_object = datetime.fromtimestamp(time_updated)
        local = pytz.timezone(tzinfo)
        local_dt = local.localize(updated_object, is_dst(tzinfo))
        utc_dt = local_dt.astimezone(pytz.utc)
        results_dict['time_updated'] = date_to_millis(updated_object)

        return results_dict


    def setup_webhook(self, token, xid):
        oauth_session = self.service.get_session(token)
        local_route = url_for("jawbone_update", jbid=xid)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        result = oauth_session.post("nudge/api/v.1.1/users/@me/pubsub?webhook=" + "<YOURBASEURL>" + local_route, headers=headers)
        return result.text


    def delete_webhook(self, token):
        oauth_session = self.service.get_session(token)
        result = oauth_session.delete("https://jawbone.com/nudge/api/v.1.1/users/@me/pubsub")
        return result.text


    def get_raw_moves(self, token, move_xid=None):
        oauth_session = self.service.get_session(token)
        if move_xid is not None:
            moves = oauth_session.get("nudge/api/v.1.1/moves/" + move_xid).json()
        else:
            moves = oauth_session.get("nudge/api/v.1.1/users/@me/moves").json()
        return moves

