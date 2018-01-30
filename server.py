from flask import Flask, request, redirect, session, g, jsonify
from flask_session import Session
from flask.ext.github import GitHub
from jwt import jwk_from_pem
from requests.auth import HTTPBasicAuth
from util import io
from util.user import User
from db import insert, fetch
from bson import ObjectId
import requests, json, urllib, pymongo, sys, secrets


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


@app.route('/login')
def login():
    if session.get('user_token', None) is None:
        return redirect('https://github.com/login/oauth/authorize?client_id=96d3befa08fccb14296c&scope=user&state=report', 200)
    else:
        response_user = requests.get("https://api.github.com/user", headers={'Authorization': 'token %s' % session.get('user_token')}).json()
        pr_db = pymongo.MongoClient().pr_database
        user_id = pr_db.report_users.insert_one(response_user).inserted_id
        return redirect('http://propr.tudelft.nl/profile.html?userid=%s' % user_id)


@app.route('/feedback')
def feedback():
    client = pymongo.MongoClient()
    pr_db = client.pr_database
    encoded_return_url = request.args.get('returnurl')
    encoded_url = request.args.get('url')
    pr_id = request.args.get('prid')
    repo_id = request.args.get('repoid')
    pr_num = request.args.get('prnum')
    is_private_repo = request.args.get('private')
    inst_id = request.args.get('instid', default='None')
    state = secrets.token_hex(12)
    feedback_url = "http://propr.tudelft.nl/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=%s&state=%s" % (encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo, inst_id, state)
    pr_db.state.insert_one({
        "_id": ObjectId(state),
        "feedback_url": feedback_url,
        "installaton_id": inst_id
        })
    if session.get('user_token', None) is None:
        return redirect('https://github.com/login/oauth/authorize?client_id=96d3befa08fccb14296c&state=%s' % state)
    else:
        user_id = insert.participant(session.get('user_token'), state)
        return redirect(feedback_url + "&userid=%s" % user_id)


@app.route('/submit', methods=['POST'])
def submit():
    if request.json["action"] == 'history':
        history = fetch.form_history(request.json["user_id"], request.json["pr_url"])
        if history is not None:
            return jsonify(history)
        else:
            return "None", 204

    elif request.json["action"] == 'feedback':
        pr_num = request.json["pr_num"]
        full_repo_name = request.json["full_repo_name"]
        insert.feedback_into_participant(request.json, request.json["state"])
        if request.json["inst_id"] != "None":
            insert.context(full_repo_name, pr_num, headers=io.get_auth_header(request.json["inst_id"], priv_key), code_privacy=request.json["code_privacy"])
        else:
            insert.context(full_repo_name, pr_num, http_auth=http_auth, code_privacy=request.json["code_privacy"])
        return 'Feedback inserted into DB', 200

    elif request.json["action"] == "moz_feedback":
        insert.moz_feedback(request.json)
        return 'Feedback inserted into DB', 200

    elif request.json["action"] == 'context':
        pr_num = request.json["pr_num"]
        full_repo_name = request.json["full_repo_name"]
        if request.json["inst_id"] != "None":
            insert.context(full_repo_name, pr_num, headers=io.get_auth_header(request.json["inst_id"], priv_key), code_privacy=request.json["code_privacy"])
        else:
            insert.context(full_repo_name, pr_num, http_auth=http_auth, code_privacy=request.json["code_privacy"])
        return 'Context inserted into DB', 200

    else:
        return 'Request not handled', 501


@app.route('/callback', methods=['GET', 'POST'])
def callback_handler():
        response = {'code': request.args.get('code'),
                    'client_id': client_config['GITHUB_CLIENT_ID'],
                    'client_secret': client_config['GITHUB_CLIENT_SECRET']}
        r = requests.post("https://github.com/login/oauth/access_token", data=response, headers={'Accept': 'application/json'})
        oauth_token = r.json()['access_token']
        state = request.args.get('state')
        if oauth_token is not None:
            session['user_token'] = oauth_token
        if state == 'report':
            response_user = requests.get("https://api.github.com/user", headers={'Authorization': 'token %s' % oauth_token}).json()
            pr_db = pymongo.MongoClient().pr_database
            user_id = pr_db.report_users.insert_one(response_user).inserted_id
            return redirect('http://propr.tudelft.nl/profile.html?userid=%s' % user_id)
        else:
            user_id = insert.participant(oauth_token, state)
            client = pymongo.MongoClient()
            pr_db = client.pr_database.state
            return redirect(pr_db.find_one({"_id": ObjectId(state)})["feedback_url"] + "&userid=%s" % user_id)


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.json is None:
        print("NULL REQUEST: " + request.headers, file=sys.stderr)
        return '', 400

    elif "action" not in request.json and request.headers['X-GitHub-Event'] == "ping":
        # POST request has initial webhook and repo details
        client = pymongo.MongoClient()
        pr_db = client.pr_database
        # Insert init repo info into DB
        pr_db.webhook_init.insert_one(request.json)
        return '', 200

    elif request.json.get("action", None) == "created" and request.headers['X-GitHub-Event'] == "installation":
        client = pymongo.MongoClient()
        pr_db = client.pr_database
        # Insert init repo info into DB
        pr_db.app_init.insert_one(request.json)
        return 'Install successful', 200

    elif request.json.get("action", None) == "closed" and request.headers['X-GitHub-Event'] == "pull_request":
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
            feedback_url = "http:/chennai.ewi.tudelft.nl:60002/feedback?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=%s" % (encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo, request.json["installation"]["id"])
            pr_comment_payload = json.dumps({"body": "Please provide your feedback on this pull request [here](%s).\n\n**Privacy statement**: We don't store any personal information such as your email address or name. We ask for GitHub authentication as an anonymous identifier to account for duplicate feedback entries and to see people specific preferences." % feedback_url})
            r = requests.post(pr_comment_url, data=pr_comment_payload, headers=io.get_auth_header(request.json["installation"]["id"], priv_key))
        else:
            feedback_url = "http:/chennai.ewi.tudelft.nl:60002/feedback?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=None" % (encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo)
            pr_comment_payload = json.dumps({"body": "Please provide your feedback on this pull request [here](%s).\n\n**Privacy statement**: We don't store any personal information such as your email address or name. We ask for GitHub authentication as an anonymous identifier to account for duplicate feedback entries and to see people specific preferences." % feedback_url})
            r = requests.post(pr_comment_url, data=pr_comment_payload, auth=http_auth)
        if not is_private_repo:
            io.download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
        return str((r.headers, r.json())), 200
    else:
        return 'Request not handled', 202


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
    if 'user_token' in session:
        g.user = User(session['user_token'])


if __name__ == '__main__':
    app.run(threaded=True)
