from os.path import dirname, abspath

SECRET_KEY = 'random-secret-key'
SESSION_COOKIE_NAME = 'psa_session'
DEBUG = True
SQLALCHEMY_DATABASE_URI = '<YOURS>'
DEBUG_TB_INTERCEPT_REDIRECTS = False
SESSION_PROTECTION = 'strong'

OAUTH_CREDENTIALS = {
    'jawbone': {
        'id': '<YOURS>',
        'secret': '<YOURS>'
    },
    'google': {
        'id': '<YOURS>',
        'secret': '<YOURS>'
    }
};
