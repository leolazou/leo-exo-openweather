from flask import Flask
from flask_restful import Resource, Api

import firebase_admin as firebase
from firebase_admin import db

# Flask app
app = Flask(__name__)
api = Api(app)

# Firebase ii
fb_cred = firebase.credentials.Certificate('key_sa_firebase.json')
firebase.initialize_app(fb_cred, {
    'databaseURL' : 'https://leo-exo-openweather.firebaseio.com/'
})

# root = db.reference('/')
users = db.reference('/users/')
items = db.reference('/items/')

class Users(Resource):
    def get(self):
        pass

if __name__ == '__main__':
     app.run()