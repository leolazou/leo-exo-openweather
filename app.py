from flask import Flask, request, json, jsonify, abort, make_response
import firebase_admin as firebase
from firebase_admin import db
from secrets import token_hex
import time

# Flask app
api = Flask(__name__)

# initialising access to Firebase DB
fb_cred = firebase.credentials.Certificate('key_sa_firebase.json')
firebase.initialize_app(fb_cred, {
    'databaseURL' : 'https://leo-exo-openweather.firebaseio.com/'
})

# db references. This retrieves no data
root = db.reference('/')
users = db.reference('/users/')
items = db.reference('/items/')


# Constants
login_token_time = 1800  # 30 minutes


# helper functions

def get_user_from_token(token):
    user = users.order_by_child('logins/token').equal_to(token).get()   
    if not user:  # check : user exists ?
        abort(make_response(jsonify({'message':'Failed. Bad token.'}), 401))
    elif len(user.values()) > 1:  # for improbable (1:10^24 for 2 users) cases when 2 users have same temporary token
        abort(make_response(jsonify({'message':'Problems with token unicity. Please login again.'}), 401))
    
    user = next(iter(user.values()))  # getting the first user
    if int(time.time()) - user['logins']['time'] > login_token_time:  # check : token not expired ?
        abort(make_response(jsonify({'message':'Failed. Expired token'}), 400))
    else:
        return user

def get_req_params(req, *req_params):
    if not req.args or not all(e in req.args for e in req_params):
        abort(make_response(jsonify({'message':'Failed. Missing parameters.'}), 400))
    return (req.args[a] for a in req_params)



# API endpoints

@api.route('/test', methods=['GET'])
def test():
    return jsonify({'message':'I am alive.'}), 217
    

@api.route('/registration', methods=['POST'])
def registration():
    login, pw = get_req_params(request, 'login', 'password')
    
    # check : user exists already ?
    if users.child(login).get() != None:
        return make_response(jsonify({'message':'User already exists.'}), 401)
    
    #create new user
    users.child(login).set({
        'id':login,
        'pw':pw
    })
    return make_response(jsonify({'message':'Registered.'}), 200)


@api.route('/login', methods=['POST'])
def login():
    login, pw = get_req_params(request, 'login', 'password')

    user_ref = users.child(login)
    token = token_hex(10)
 
    if user_ref.get()['pw'] != pw:
        return make_response(jsonify({"message":"Wrong password."}), 401)

    user_ref.update({
        'logins':{
            'token':token,
            'time':int(time.time())
        }
    })
    return make_response(jsonify({"message":"Logged in.","token":token}), 200)    

@api.route('/items/new', methods=['POST'])
def new_item():
    item, token = get_req_params(request, 'item', 'token')
    user = get_user_from_token(token)
    
    new_item = items.push({
        'user':user['id'],
        'item':item
    })
    return make_response(jsonify({
            'message':'Item added.',
            'item_id':new_item.key,
            'item':item
        }), 200)
    
@api.route('/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    token, = get_req_params(request, 'token')
    user = get_user_from_token(token)

    if user['id'] != items.child(item_id).get()['user']:  # if item owner differs from token owner
        return make_response(jsonify({'message':'Failed. Bad token.'}), 400)

    items.child(item_id).delete()
    return make_response(jsonify({'message':'Item deleted.'}), 200)

@api.route('/items', methods=['GET'])
def list_user_items():
    token, = get_req_params(request, 'token')
    user = get_user_from_token(token)

    # getting user's items and showing in the form of a list
    user_items = [ {'id':k,'item':v['item']}
        for k,v in items.order_by_child('user').equal_to(user['id']).get().items() ]

    return make_response(jsonify({
            "login":user['id'],
            "items": user_items
        }), 200)

@api.route('/send', methods=['POST'])
def send_item():
    item_id, rceiver_id, user_token = get_req_params(request, 'item_id', 'receiver', 'token')
    user = get_user_from_token(user_token)

    receiver = users.child(rceiver_id).get()
    if not receiver:
        return make_response(jsonify({'message':'Fail. Receiver doesn\'t exist.'}), 400)

    item_ref = items.child(item_id)
    item = item_ref.get()
    if not item or item['user'] != user['id']:
        return make_response(jsonify({'message':'Fail. No such item exists.'}), 400)
    
    send_token = token_hex(10)
    url = request.url_root +'receive' + '?item_id=' + item_id + '&token=' + send_token

    # unders send/ attribute creating a new send token for each send (so that 1 item can be sent to mult users)
    item_ref.child('send').child(send_token).set({
        'receiver':receiver['id'],
        'time':int(time.time()),
        'expires':int(time.time()) + 86400,  # 1 day
        'status':'sent'
    })

    return make_response(jsonify({
        'message':'Item sent.',
        'url':url
    }))

@api.route('/receive/', methods=['GET'])
def receive_item():
    item_id, token = get_req_params(request, 'item_id', 'token')
    item_ref = items.child(item_id)
    item = item_ref.get()

    if not item:
        return make_response(jsonify({'massage':'Fail. Item not found.'}), 404)
    elif token not in item['send']:
        return make_response(jsonify({'message':'Fail. Unauthorised.'}), 401)
    elif int(time.time()) > item['send'][token]['expires']:
        item_ref.child('send/'+token).update({'status':'late for delivery'})  # updating status
        return make_response(jsonify({'message':'Fail. You\'re late for delivery.'}), 401)
    else:
        item_ref.child('send/'+token).update({'status':'received'})
        return make_response(jsonify({'message':'Success. Item received.'}), 200)

@api.errorhandler(404)
@api.errorhandler(405)
def not_found(e):
    return make_response(jsonify({'message':'Test project. Refer to Readme on Github.'}), 404)

if __name__ == '__main__':
    api.run()