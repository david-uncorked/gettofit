from rauth import OAuth1Service, OAuth2Service
from flask import current_app, url_for, request, redirect, session
from fit_templates import fit_datasource_template, fit_dataset_meta_template, fit_dataset_point_template, fit_session_template
import urllib2
import json
import logging
from random import randint

def random_with_N_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)


class OAuthProvider(object):
    providers = None

    def __init__(self, provider_name):
        self.provider_name = provider_name
        credentials = current_app.config['OAUTH_CREDENTIALS'][provider_name]
        self.consumer_id = credentials['id']
        self.consumer_secret = credentials['secret']

    def authorize(self):
        pass

    def callback(self):
        pass

    def get_callback_url(self):
        return url_for('oauth_callback', provider=self.provider_name,
                       _external=True)

    @classmethod
    def get_provider(self, provider_name):
        if self.providers is None:
            self.providers = {}
            for provider_class in self.__subclasses__():
                provider = provider_class()
                self.providers[provider.provider_name] = provider
        return self.providers[provider_name]



class GoogleSignIn(OAuthProvider):
    def __init__(self):
        super(GoogleSignIn, self).__init__('google')
        googleinfo = urllib2.urlopen('https://accounts.google.com/.well-known/openid-configuration')
        google_params = json.load(googleinfo)
        self.service = OAuth2Service(
                name='google',
                client_id=self.consumer_id,
                client_secret=self.consumer_secret,
                authorize_url=google_params.get('authorization_endpoint'),
                base_url=google_params.get('userinfo_endpoint'),
                access_token_url=google_params.get('token_endpoint')
        )

    def refresh(self, refresh_token):
        oauth_session_data = self.service.get_raw_access_token(
            data={'client_id': self.consumer_id,
            'client_secret': self.consumer_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token}
        )
        oauth_session_json = oauth_session_data.json()
#        logging.info(oauth_session_data.text)
        if 'access_token' not in oauth_session_json:
            return None
        token = oauth_session_json['access_token']
        return token


    def get_callback_url(self):
        return url_for('oauth_callback',
                       _external=True)

    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='email https://www.googleapis.com/auth/fitness.activity.read https://www.googleapis.com/auth/fitness.activity.write',
            response_type='code',
            access_type='offline',
            redirect_uri=self.get_callback_url())
            )

    def callback(self):
        if 'code' not in request.args:
            return None, None, None

        oauth_session_data = self.service.get_raw_access_token(
            data={'code': request.args['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': self.get_callback_url()}
        )

        oauth_session_json = oauth_session_data.json()
        token = oauth_session_json['access_token']
        if 'refresh_token' not in oauth_session_json:
            refresh_token = None
        else:
	        refresh_token = oauth_session_json['refresh_token']


        oauth_session = self.service.get_session(token)

        me = oauth_session.get('').json()
        return (me['sub'],
                me['name'],
                me['email'],
                oauth_session.access_token,
                refresh_token)

    def setup_datasource(self, refresh_token, access_token):
        new_access_token = self.refresh(refresh_token)
        if new_access_token:
           access_token = new_access_token
        ds_temp = json.loads(fit_datasource_template)
        ds_temp['device']['uid'] = str(random_with_N_digits(5))
        oauth_session = self.service.get_session(access_token)
        headers = {'Content-Type': 'application/json'}
        result = oauth_session.post("https://www.googleapis.com/fitness/v1/users/me/dataSources", json.dumps(ds_temp), headers=headers).json()
        return (access_token, result['dataStreamId'])

    def send_moves_to_fit(self, moves, datasource_id, refresh_token, access_token):
        new_access_token = self.refresh(refresh_token)
        if new_access_token:
           access_token = new_access_token
        ds_temp = json.loads(fit_dataset_meta_template)
        sessions = dict()
        min_nanos = None
        max_nanos = 0
#        logging.info(str(datasource_id))
        for key, value in iter(sorted(moves.iteritems())):
            point_temp = json.loads(fit_dataset_point_template)
            end_nanos=long(key) + 3600000
            point_temp['endTimeNanos']=end_nanos
            point_temp['startTimeNanos']=key
            if not min_nanos:
               min_nanos = long(key)
            point_temp['value'][0]['intVal']=value
            ds_temp["point"].append(point_temp)
            session_temp = json.loads(fit_session_template)
            session_id= "get-to-fit-steps-" + str(key) + "-" + str(random_with_N_digits(5))
            session_temp["id"] = session_id
            session_temp["startTimeMillis"]=long(key)/1000000
            session_temp["endTimeMillis"]=end_nanos/1000000

            sessions[session_id]=session_temp
            if min_nanos > long(key):
               min_nanos = long(key)
            if max_nanos < end_nanos:
               max_nanos = end_nanos

        ds_temp['minStartTimeNs'] = min_nanos
        ds_temp['maxEndTimeNs'] = max_nanos
        ds_temp['dataSourceId'] = datasource_id
        oauth_session = self.service.get_session(access_token)
        patchurl = 'https://www.googleapis.com/fitness/v1/users/me/dataSources/' + datasource_id + '/datasets/' + str(min_nanos) + '-' + str(max_nanos)
        headers = {'Content-Type': 'application/json'}
        result = oauth_session.patch(patchurl, json.dumps(ds_temp), headers=headers)
#        logging.info(result.text)

        for key, value in sessions.iteritems():
            puturl = 'https://www.googleapis.com/fitness/v1/users/me/sessions/' + key
            result = oauth_session.put(puturl, json.dumps(value), headers=headers)
#            logging.info(result.text)
        return "Complete " + str(result)


