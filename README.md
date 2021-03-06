Test task for OpenWeather by Leo
=======


## TLDR

Goal: Create a simple API. Result: API deployed to Google App Engine, can be accessed [here](https://leo-exo-openweather.nw.r.appspot.com/). Or clone and run the `api.py` file manually.


## Tech stack

- **Python 3**
- **Flask** is used to create a simple server
- **Firebase Realtime DB** to store the data. Firebase is chosen over a local SQL/NoSQL server to better simulate a real world cloud DB. Firebase over other cloud solutions mainly because it's fast to set up and simple to use. *firebase_admin* python package lets read/write to the DB from python code and automatically detects data types.
- **Google App Engine** to deploy the API on the web and make it accessible without the need to create local Flask server. The latter is also possible.
- **Git**


## How to access

The API is deployed to Google App Engine. So you can access it on : https://leo-exo-openweather.nw.r.appspot.com/

You can also run it on your PC. Go to the code location.
* install requiresd python packages:
  * if you use *pipenv* run `pipenv install` then `pipenv shell`
  * else, use `pip install -r requirements.txt`
* run `python3 api.py`

The address to access API will be shown in the console. Should be <http://127.0.0.1:5000>.


## API endpoints

All params in the query string.
Responses are JSON.

### **/test** | method: GET | parameters: None
Tests if API alive at all

### **/registration** | POST | params: *login, password*
Creates new user if the login doesn't exit already.

### **/login** | POST | params: *login, password*
Logins the user. Returns a temporary token which is active for 30 minuts. Use this token in the next queries.

### **/items/new** | POST | params: *tokem, item*
Adds a new item to user (identified via *token*). Returns the item ID (auto generated by Firebase).

### **/items/<item_id>** | DELETE | params: *token*
Deletes the item (found with *item_id*) from user if the *token* is correct.

### **/items** | GET | params: *token*
Lists items of the user (identified via *token*).

### **/send** | POST | params: *token, item_id, receiver*
Sends an item belonging to the user to the receiver. Generates a link that lets receive the item in the next 24 hours. *item_id* should be a valid id of an item belonging to the user (identified via *token*). *receiver* should be a login of an exisitn user. One item can be sent multiple times simultaneously.

### **/receive** | GET | params: *item_id, token*
Makes you receive the item. No login required. *item_id* is the item that is being sent, *token* is the temporary token of the transmission generated in the link above (not a login token). In case of success, informs that item is received and also logs it in the DB.

## DataBase

In the Firebase DB data is structured as follows :

```json
{
    "users":{
        "spacex":{  // id
            "id":"spacex",
            "pw":"2Mars",
            "logins":{
                "token":"105826e38a505c0f7f5d",
                "time":"1590679842" //timestamp
            }
        },
        "mike":{} // ...
    },
    "items":{
        "-M8QxfNJKGnlebTYs2ET":{  // item id
            "item":"falcon heavy",
            "user":"spacex",
            "send":{
                "4734c4528a7ecbbb7014":{  // send token
                    "receiver":"mia",
                    "status":"received",
                    "time":"1590680851",
                    "expires":"1590767251"
                }
            }
        },
        "-M8L8YwF3uiJehjSi0pS":{}
    }
}
```

## Remarks

* login & password could have been encrypted
* *app.yaml* file is for deployment to App Egine. so is the *gunicorn* module
* putting a Firebase service account key on a public github ain't such a good idea. But necessary to run the api on a local machine. It also has minimum necessary permissions.
* currently the code lacks `try+except` blocks. Instead, errors are caught by `@api.errorhandler` and a very non informative fail message is returned.
* user can have 1 simultaneous login max
* DB structure can of course be discussed