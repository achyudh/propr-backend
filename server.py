from flask import Flask, request, abort, redirect, session, g
from flask_session import Session
from requests.auth import HTTPBasicAuth
import requests, json, urllib, pymongo, sys, datetime
from flask_github import GitHub
from util.user import User
import python_jwt as jwt
import Crypto.PublicKey.RSA as RSA


app = Flask(__name__)
sess = Session()
with open("config.json", 'r') as config_file:
    client_config = json.load(config_file)

app.config['SESSION_TYPE'] = 'mongodb'
app.config['GITHUB_CLIENT_ID'] = client_config['GITHUB_CLIENT_ID']
app.config['GITHUB_CLIENT_SECRET'] = client_config['GITHUB_CLIENT_SECRET']
app.secret_key = client_config['APP_SECRET']
http_auth_username = client_config['HTTP_AUTH_USERNAME']
http_auth_secret = client_config['HTTP_AUTH_SECRET']
sess.init_app(app)
github = GitHub(app)


@app.route('/login')
def login():
    with open("private-key.pem", 'r') as priv_key_file:
        priv_key = RSA.importKey(priv_key_file)
    payload = {"iss": "42 5168"}
    token = jwt.generate_jwt(payload, priv_key, 'RS256', datetime.timedelta(minutes=10))

    if session.get('user_id', None) is None:
        return github.authorize(scope="user, repo")
    else:
        return 'User already logged in', 200


@app.route('/callback')
@github.authorized_handler
def callback_handler(oauth_token):
    print("HANDLER", oauth_token, file=sys.stderr)
    if oauth_token is None:
        return redirect("http://dutiap.st.ewi.tudelft.nl:60001/nextsteps.html?success=False")
    else:
        client = pymongo.MongoClient()
        user_coll = client.user_database.oauth_tokens
        user = User.find_by_token(oauth_token, user_coll)
        if user is None:
            user = User(oauth_token)
            # Add user to DB if not already present
            user.insert_into_db(user_coll)
        session['user_id'] = user.id
        return redirect("http://dutiap.st.ewi.tudelft.nl:60001/nextsteps.html?success=True")


@app.route('/webhook', methods=['POST'])
def webhook():
    http_auth = HTTPBasicAuth(http_auth_username, http_auth_secret)
    if request.method == 'POST':
        if request.json is None:
            print("NULL REQUEST: " + request.headers, file=sys.stderr)
            return '', 500

        elif "zen" in request.json:
            # POST request has initial webhook and repo details
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            # Insert init repo info into DB
            pr_db.webhook_init.insert_one(request.json)
            return '', 200

        elif request.json["action"] == "closed":
            parsed_json = request.json
            is_private_repo = request.json["pull_request"]["base"]["repo"]["private"]
            pr_num = parsed_json["pull_request"]["number"]
            pr_id = parsed_json["pull_request"]["id"]
            repo_id = parsed_json["pull_request"]["base"]["repo"]["id"]

            # Only part of the repo URL is encoded: the owner and repo name
            encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["base"]["repo"]["full_name"])
            # This is the entire URL of the PR to which the user iis redirected to once the form is filled
            encoded_return_url = urllib.parse.quote_plus(parsed_json["pull_request"]["html_url"])
            feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s" % (encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo)
            # Send POST request to comment on the PR with feedback link
            pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
            if is_private_repo:
                # pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments?access_token=%s' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], pr_num, token_getter())
                # print(requests.get(pr_comment_url, data=pr_comment_payload), file=sys.stderr)
                print(token_getter()+github.get("user"), file=sys.stderr)
            else:
                pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], pr_num)
                requests.post(pr_comment_url, data=pr_comment_payload, auth=http_auth)
                download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
            return '', 200

        elif request.json["action"] == "submit":
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            pr_num = request.json["pr_num"]
            full_repo_name = request.json["full_repo_name"]
            if request.json["is_private_repo"]:
                insert_into_db_private(pr_db, http_auth, full_repo_name, pr_num)
                return '', 200
            else:
                insert_into_db_public(pr_db, http_auth, full_repo_name, pr_num)

    else:
        abort(400)


@app.route('/redir', methods=['POST'])
def redir():
    if request.method == 'POST':
        redirect(request.json['url'], code=302)


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


@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = 'http://dutiap.st.ewi.tudelft.nl:60001'
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
        headers = request.headers.get('Access-Control-Request-Headers')
        if headers:
            response.headers['Access-Control-Allow-Headers'] = headers
    return response


def download_patch(url, http_auth, pr_id, repo_id):
    response_data = requests.get(url, auth=http_auth)
    if response_data.status_code == 200:
        with open('patches/%s-%s.txt' % (pr_id, repo_id), 'wb') as f:
            f.write(response_data.content)
    else:
        print("Error downloading patch: Status Code " + response_data.status_code)


def insert_into_db_public(pr_db, http_auth, full_repo_name, pr_num):
    # Insert feedback into DB
    del request.json["action"]
    pr_db.pr_feedback.insert_one(request.json)

    # Insert PR info into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    pr_db.pr_info.insert_one(response_json)

    # Insert commits into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/commits' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_commits.insert_many(response_json)

    # Insert PR comments into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/comments' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_comments.insert_many(response_json)

    # Insert PR reviews into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/reviews' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_reviews.insert_many(response_json)

    # Insert issue comments into DB
    request_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.issue_comments.insert_many(response_json)

    # Insert patch and files into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/files' % (full_repo_name, pr_num)
    response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_files.insert_many(response_json)


def insert_into_db_private(pr_db, http_auth, full_repo_name, pr_num):
    # Insert patch and files into DB if dev allows
    if not request.json["code_privacy"]:
        request_url = 'https://api.github.com/repos/%s/pulls/%s/files' % (full_repo_name, pr_num)
        response_json = requests.get(request_url, auth=http_auth).json()
        if len(response_json) > 0:
            pr_db.pr_files.insert_many(response_json)


if __name__ == '__main__':
    app.run()
