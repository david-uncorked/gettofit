from flask import Flask, request, redirect, url_for, render_template, json, jsonify
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, UserMixin, login_user, logout_user, current_user
from oauth import OAuthProvider
from jawbone import JawboneOAuthAdapter
import logging
import pytz
from datetime import datetime, timedelta

app = Flask(__name__)
app.config.from_object('settings')

db = SQLAlchemy(app)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    jawbone_id = db.Column(db.String(64), nullable=True, unique=True)
    google_id = db.Column(db.String(64), nullable=True, unique=True)
    google_token = db.Column(db.String(200), nullable=True, unique=True)
    google_refresh_token = db.Column(db.String(200), nullable=True, unique=True)
    fit_datasource_id = db.Column(db.String(200), nullable=True, unique=True)
    jawbone_token = db.Column(db.String(200), nullable=True, unique=True)
    jawbone_refresh_token = db.Column(db.String(200), nullable=True, unique=True)
    nickname = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(64), nullable=True)

    def has_jawbone_auth(self):
        return self.jawbone_token

    def has_google_auth(self):
        return self.google_token


db.create_all()
lm = LoginManager(app)
lm.login_view = 'index'


@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/images/<path:path>')
def send_image(path):
    return send_from_directory('images', path)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    oauth = OAuthProvider.get_provider(provider)
    return oauth.authorize()

@app.route('/callback/jawbone')
def oauth_jawbone_callback():
    if current_user.is_anonymous():
        return redirect(url_for('index'))
    oauth = OAuthProvider.get_provider('jawbone')
    jb_token, jb_refresh = oauth.callback()
    if jb_token is None:
        flash('Authentication failed.')
        return redirect(url_for('index'))

    social_id, username = oauth.get_user(jb_token)
    user = User.query.filter_by(google_id=current_user.google_id).first()

    user.nickname=username
    user.jawbone_token = jb_token
    user.jawbone_id = social_id
    user.jawbone_refresh_token = jb_refresh
    db.session.commit()

    if user.google_token is not None:
        if user.fit_datasource_id is None:
            googleadapter = OAuthProvider.get_provider('google')
            token, datasourceid = googleadapter.setup_datasource(user.google_refresh_token, user.google_token)
            if datasourceid:
                user.google_token = token
                user.fit_datasource_id = datasourceid
                db.session.commit()
    else:
        return "FAILED"
    login_user(user, True)
    return redirect(url_for('index'))


@app.route('/update/jawbone', methods=['POST', 'GET'])
def jawbone_updater():
    try: 
       requestbody = request.data
    except Exception, e:
       return "Error", 500

    notifications = json.loads(requestbody)
    if not notifications.has_key('events'):
       return "Fail", 500

    events = notifications["events"]
    respstring = ""
    for val in events:
        if not val.has_key('user_xid'):
           return "Fail", 500
        if not val.has_key('type'):
           return "Fail", 500
        if not val.has_key('event_xid'):
           return "Fail", 500

        user_xid = val["user_xid"]
        user = User.query.filter_by(jawbone_id=user_xid).first()
        if user is None:
            return "FAIL", 404

        action_type = val["type"]
        if action_type is not None:
           if action_type == "move":
               #this is a move event, so lets resovle it
               move_xid = val["event_xid"]
               jawbone_oauth = OAuthProvider.get_provider('jawbone')
               google_oauth = OAuthProvider.get_provider('google')
               moves = jawbone_oauth.get_one_move(user.jawbone_token, move_xid)
               if moves is None:
                  return "FAILED", 404
               google_oauth.send_moves_to_fit(moves, user.fit_datasource_id, user.google_refresh_token, user.google_token)
           if action_type == "user_data_deletion":
               #delete user data
               db.session.delete(user)
               db.session.commit()
    return respstring, 200


@app.route('/update/xid/jawbone/<jbid>', methods=['POST', 'GET'])
def jawbone_update(jbid):
    if jbid is not None:
        user = User.query.filter_by(jawbone_id=jbid).first()
        try: 
           requestbody = request.data
        except Exception, e:
           return "Error", 500

        notifications = json.loads(requestbody)
        if not notifications.has_key('events'):
           return "Fail", 500
        events = notifications["events"]
        respstring = ""
        for val in events:
            if not val.has_key('user_xid'):
               return "Fail", 500
            if not val.has_key('type'):
               return "Fail", 500
            if not val.has_key('event_xid'):
               return "Fail", 500

            user_xid = val["user_xid"]
            action_type = val["type"]
            if action_type is not None:
               if action_type == "move":
                   #this is a move event, so lets resovle it
                   if user is None:
                      return "FAILED", 404
                   move_xid = val["event_xid"]
                   jawbone_oauth = OAuthProvider.get_provider('jawbone')
                   google_oauth = OAuthProvider.get_provider('google')
                   moves = jawbone_oauth.get_one_move(user.jawbone_token, move_xid)
                   if moves is None:
                      return "FAILED", 404
                   google_oauth.send_moves_to_fit(moves, user.fit_datasource_id, user.google_refresh_token, user.google_token)
               if action_type == "user_data_deletion":
                   #delete user data
                   db.session.delete(user)
                   db.session.commit()
                   return "OK", 200
        return respstring, 200
    else:
        return "Fail", 404


@app.route('/callback/google')
def oauth_callback():
    oauth = OAuthProvider.get_provider('google')
    social_id, username, email, g_token, g_refresh = oauth.callback()
    if g_token is None:
        flash('Authentication failed.')
        return redirect(url_for('index'))
    user = User.query.filter_by(google_id=social_id).first()
    if not user:
        user = User(google_id=social_id, nickname=username, email=email, google_token=g_token, google_refresh_token=g_refresh)
        db.session.add(user)
        db.session.commit()
    else:
        user.email=email
        user.google_token = g_token
        if g_refresh is not None:
           user.google_refresh_token = g_refresh
        db.session.commit()
    login_user(user, True)
    return redirect(url_for('index'))

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
