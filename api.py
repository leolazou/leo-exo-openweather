from flask import Flask, request, json, jsonify, abort, make_response
import firebase_admin as firebase
from firebase_admin import db
from secrets import token_hex
import time


### Some initialization

# Flask app
api = Flask(__name__)

# initialising access to Firebase DB
fb_cred = firebase.credentials.Certificate('key_sa_firebase.json')
firebase.initialize_app(fb_cred, {
    'databaseURL' : 'https://leo-exo-openweather.firebaseio.com/'
})

# DB references. This retrieves no data
# Calls to Firebase are performed when calling get(), set(), update(), push(), and delete()
root = db.reference('/')
users = db.reference('/users/')
items = db.reference('/items/')



### Constants

login_token_time = 1800  # 30 minutes



### Helper functions

def get_user_from_token(token):
    # retrieves the user (json) from a login token
    user = users.order_by_child('logins/token').equal_to(token).get()  # retuerns a list of users matching the query
    if not user:  # check : user exists ?
        abort(make_response(jsonify({'message':'Failed. Bad token.'}), 401))
    elif len(user.values()) > 1:  # for improbable (1:10^24 for 2 users) cases when 2 users have same temporary token
        abort(make_response(jsonify({'message':'Problems with token unicity. Please login again.'}), 401))
    
    user = next(iter(user.values()))  # getting the first user
    if int(time.time()) - user['logins']['time'] > login_token_time:  # check : token not expired ?
        abort(make_response(jsonify({'message':'Failed. Expired token'}), 401))
    else:
        return user

def get_req_params(req, *req_params):
    # checking if all request parameters are present then returning their values
    if not req.args or not all(e in req.args for e in req_params):
        abort(make_response(jsonify({'message':'Failed. Missing parameters.'}), 400))
    return (req.args[a] for a in req_params)



### API endpoints

@api.route('/test', methods=['GET'])  # kind of ping
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
    user = user_ref.get()
    token = token_hex(10)

    if not user:
        return make_response(jsonify({"message":"No such user exists."}), 401)
    elif user['pw'] != pw:
        return make_response(jsonify({"message":"Wrong password."}), 401)

    # saving token & login time to DB
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
    
    # saving new item to DB. item id (key) automatically generated
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
    item = items.child(item_id).get()

    if not item:
        return make_response(jsonify({'message':'No such item exists.'}), 200)

    # checking that item owner is token owner
    if user['id'] != item['user']:
        return make_response(jsonify({'message':'Failed. Bad token.'}), 400)

    # deleting item from DB
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

    # adds send/ attribute creating a new send token for each send (so that 1 item can be sent to mult users)
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

    if not item:  # if no item with given id found
        return make_response(jsonify({'massage':'Fail. Item not found.'}), 404)
    elif token not in item['send']:  # if wrong token
        return make_response(jsonify({'message':'Fail. Unauthorised.'}), 401)
    elif int(time.time()) > item['send'][token]['expires']:  # if token expired
        # updating status to inform that the receiver tried to get the item but token expired
        item_ref.child('send/'+token).update({'status':'late for delivery'})
        return make_response(jsonify({'message':'Fail. You\'re late for delivery.'}), 401)
    else:
        # updating status to inform that the receiver received the item
        item_ref.child('send/'+token).update({'status':'received'})
        return make_response(jsonify({'message':'Success. Item received.'}), 200)


# Errors
@api.errorhandler(404)  # all other paths
@api.errorhandler(405)  # bad method used
def not_found(e):
    return make_response(jsonify({'message':'Test project. Refer to Readme on Github.'}), 404)

@api.errorhandler(Exception)  # server problems
def error(e):
    return make_response(jsonify({'message':'Something went wrong...'}), 500)


if __name__ == '__main__':
    api.run()