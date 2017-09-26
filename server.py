from flask import Flask, request, redirect, session, jsonify, g
from flask_session import Session
from flask.ext.github import GitHub
from jwt import JWT, jwk_from_pem
from requests.auth import HTTPBasicAuth
from util import io
from util.user import User
from bson.objectid import ObjectId
from db import handler
import requests, json, urllib, pymongo, sys, time, hashlib


app = Flask(__name__)
sess = Session()
with open("config.json", 'r') as config_file:
    client_config = json.load(config_file)
with open("private-key.pem", 'rb') as priv_key_file:
    priv_key = jwk_from_pem(priv_key_file.read())
http_auth_username = client_config['HTTP_AUTH_USERNAME']
http_auth_secret = client_config['HTTP_AUTH_SECRET']
http_auth = HTTPBasicAuth(http_auth_username, http_auth_secret)
app.config['SESSION_TYPE'] = 'mongodb'
app.config['GITHUB_CLIENT_ID'] = client_config['GITHUB_CLIENT_ID']
app.config['GITHUB_CLIENT_SECRET'] = client_config['GITHUB_CLIENT_SECRET']
sess.init_app(app)
github = GitHub(app)


@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST' and request.json["action"] == 'feedback':
        client = pymongo.MongoClient()
        pr_db = client.pr_database
        pr_num = request.json["pr_num"]
        full_repo_name = request.json["full_repo_name"]
        if request.json["inst_id"] != "None":
            state = handler.insert(request, pr_db, full_repo_name, pr_num, headers=get_auth_header(request.json["inst_id"]),
                              code_privacy=request.json["code_privacy"])
        else:
            state = handler.insert(request, pr_db, full_repo_name, pr_num, http_auth=http_auth,
                              code_privacy=request.json["code_privacy"])
        return 'https://github.com/login/oauth/authorize?client_id=96d3befa08fccb14296c&scope=user&state=%s' % state, 200
    else:
        return 'Request not handled', 501


@app.route('/callback', methods=['GET', 'POST'])
def callback_handler():
    client = pymongo.MongoClient()
    response = {'code': request.args.get('code'),
                'client_id': client_config['GITHUB_CLIENT_ID'],
                'client_secret': client_config['GITHUB_CLIENT_SECRET']}
    r = requests.post("https://github.com/login/oauth/access_token", data=response, headers={'Accept': 'application/json'})
    oauth_token = r.json()['access_token']
    if oauth_token is not None:
        user_coll = client.user_database.oauth_tokens
        user = User.find_by_token(oauth_token, user_coll)
        if user is None:
            user = User(oauth_token)
            # Add user to DB if not already present
            user.insert_into_db(user_coll)
        session['user_id'] = user.id
    response_user = requests.get("https://api.github.com/user", headers={'Authorization': 'token %s' % oauth_token}).json()
    user_info = {
        "id": hashlib.sha256(str.encode(response_user["login"])).hexdigest(),
        "public_repos": response_user["public_repos"],
        "public_gists": response_user["public_gists"],
        "followers": response_user["followers"],
        "following": response_user["following"],
        "created_at": response_user["created_at"],
        "updated_at": response_user["updated_at"],
        "private_gists": response_user["private_gists"],
        "total_private_repos": response_user["total_private_repos"],
        "owned_private_repos": response_user["owned_private_repos"],
        "collaborators": response_user["collaborators"]
    }
    feedback_coll = client.pr_database.pr_feedback
    result = feedback_coll.find_one({"_id": ObjectId(request.args.get('state'))})
    feedback_coll.update_one(
        {"_id": ObjectId(request.args.get('state'))},
        {'$set': {'user': user_info}}
    )
    if result['pr_url'] is not None:
        return redirect(result['pr_url'])
    else:
        return "DB entry not found", 500


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        if request.json is None:
            print("NULL REQUEST: " + request.headers, file=sys.stderr)
            return '', 500

        elif "action" not in request.json and request.headers['X-GitHub-Event'] == "ping":
            # POST request has initial webhook and repo details
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            # Insert init repo info into DB
            pr_db.webhook_init.insert_one(request.json)
            return '', 200

        elif request.json["action"] == "created" and request.headers['X-GitHub-Event'] == "installation":
            return 'Install successful', 200

        elif request.json["action"] == "closed" and request.headers['X-GitHub-Event'] == "pull_request":
            parsed_json = request.json
            is_private_repo = request.json["pull_request"]["base"]["repo"]["private"]
            pr_num = parsed_json["pull_request"]["number"]
            pr_id = parsed_json["pull_request"]["id"]
            repo_id = parsed_json["pull_request"]["base"]["repo"]["id"]

            # Only part of the repo URL is encoded: the owner and repo name
            encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["base"]["repo"]["full_name"])
            # This is the entire URL of the PR to which the user iis redirected to once the form is filled
            encoded_return_url = urllib.parse.quote_plus(parsed_json["pull_request"]["html_url"])
            # Send POST request to comment on the PR with feedback link
            pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], pr_num)
            if "installation" in request.json:
                feedback_url = "http:/chennai.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=%s" % (
                encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo, request.json["installation"]["id"])
                pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
                r = requests.post(pr_comment_url, data=pr_comment_payload, headers=get_auth_header(request.json["installation"]["id"]))
            else:
                feedback_url = "http:/chennai.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=None" % (
                encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo)
                pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
                r = requests.post(pr_comment_url, data=pr_comment_payload, auth=http_auth)
                if not is_private_repo:
                    io.download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
            return str((r.headers, r.json())), 200
        else:
            return 'Request not handled', 501
    else:
        return 'Not a POST request', 405


@app.route('/redir', methods=['POST'])
def redir():
    if request.method == 'POST':
        redirect(request.json['url'], code=302)


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
        headers = request.headers.get('Access-Control-Request-Headers')
        if headers:
            response.headers['Access-Control-Allow-Headers'] = headers
    return response


@github.access_token_getter
def token_getter():
    user = g.user
    if user is not None:
        return user.github_access_token


@app.before_request
def before_request():
    g.user = None
    client = pymongo.MongoClient()
    user_coll = client.user_database.oauth_tokens
    if 'user_id' in session:
        g.user = User.find_by_id(session['user_id'], user_coll)


def get_auth_header(installation_id):
    payload = {"iss": 5168,
               "iat": int(time.time()),
               "exp": int(time.time()) + 300}
    jwt = JWT()
    token = jwt.encode(payload, priv_key, 'RS256')
    # url = "https://api.github.com/app"
    url = "https://api.github.com/installations/%s/access_tokens" % installation_id
    headers = {'Accept': 'application/vnd.github.machine-man-preview+json',
               'Authorization': 'Bearer ' + token}
    r = requests.post(url, headers=headers)
    ret_headers = {"Authorization": "token " + r.json()["token"],
                   "Accept": "application/vnd.github.machine-man-preview+json"}
    return ret_headers


if __name__ == '__main__':
    app.run()
