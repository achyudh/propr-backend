from flask import Flask, request, abort, redirect, session, g
from flask_session import Session
from requests.auth import HTTPBasicAuth
import requests, json, urllib, pymongo, sys
import time
from jwt import JWT, jwk_from_dict, jwk_from_pem
import Crypto.PublicKey.RSA as RSA


app = Flask(__name__)
sess = Session()
with open("config.json", 'r') as config_file:
    client_config = json.load(config_file)
with open("private-key.pem", 'rb') as priv_key_file:
    priv_key = jwk_from_pem(priv_key_file.read())
app.config['SESSION_TYPE'] = 'mongodb'
app.secret_key = client_config['APP_SECRET']
http_auth_username = client_config['HTTP_AUTH_USERNAME']
http_auth_secret = client_config['HTTP_AUTH_SECRET']
sess.init_app(app)


@app.route('/webhook', methods=['POST'])
def webhook():
    http_auth = HTTPBasicAuth(http_auth_username, http_auth_secret)
    if request.method == 'POST':
        if request.json is None:
            print("NULL REQUEST: " + request.headers, file=sys.stderr)
            return '', 500

        elif request.headers['X-GitHub-Event'] == "ping":
            # POST request has initial webhook and repo details
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            # Insert init repo info into DB
            pr_db.webhook_init.insert_one(request.json)
            return '', 200

        elif request.headers['X-GitHub-Event'] == "installation" and request.json["action"] == "created":
            return 'Install successful', 200

        elif request.headers['X-GitHub-Event'] == "pull_request" and request.json["action"] == "closed":
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
                feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=%s" % (
                encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo, request.json["installation"]["id"])
                pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
                requests.post(pr_comment_url, data=pr_comment_payload, headers=get_auth_header(request.json["installation"]["id"]))
            else:
                feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s&instid=None" % (
                encoded_return_url, encoded_url, pr_id, repo_id, pr_num, is_private_repo)
                pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
                requests.post(pr_comment_url, data=pr_comment_payload, auth=http_auth)
                download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
            return '', 200

        elif request.json["action"] == "submit":
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            pr_num = request.json["pr_num"]
            full_repo_name = request.json["full_repo_name"]
            if request.json["inst_id"] != "None":
                insert_into_db(pr_db, full_repo_name, pr_num, headers=get_auth_header(request.json["inst_id"]), code_privacy=request.json["code_privacy"])
            else:
                insert_into_db(pr_db, full_repo_name, pr_num, http_auth=http_auth, code_privacy=request.json["code_privacy"])
            return '', 200
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
    response.headers['Access-Control-Allow-Origin'] = 'http://dutiap.st.ewi.tudelft.nl:60001'
    if request.method == 'OPTIONS':
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
        headers = request.headers.get('Access-Control-Request-Headers')
        if headers:
            response.headers['Access-Control-Allow-Headers'] = headers
    return response


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


def download_patch(url, http_auth, pr_id, repo_id):
    response_data = requests.get(url, auth=http_auth)
    if response_data.status_code == 200:
        with open('patches/%s-%s.txt' % (str(pr_id), str(repo_id)), 'wb') as f:
            f.write(response_data.content)
    else:
        print("Error downloading patch: Status Code " + response_data.status_code)


def insert_into_db(pr_db, full_repo_name, pr_num, http_auth=None, headers=None, code_privacy=False):
    # Insert feedback into DB
    del request.json["action"]
    pr_db.pr_feedback.insert_one(request.json)

    # Insert PR info into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    pr_db.pr_info.insert_one(response_json)

    # Insert commits into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/commits' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_commits.insert_many(response_json)

    # Insert PR comments into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/comments' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_comments.insert_many(response_json)

    # Insert PR reviews into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/reviews' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.pr_reviews.insert_many(response_json)

    # Insert issue comments into DB
    request_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    if len(response_json) > 0:
        pr_db.issue_comments.insert_many(response_json)

    # Insert patch and files into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/files' % (full_repo_name, pr_num)
    if not code_privacy:
        if headers is not None:
            response_json = requests.get(request_url, headers=headers).json()
        else:
            response_json = requests.get(request_url, auth=http_auth).json()
        if len(response_json) > 0:
            pr_db.pr_files.insert_many(response_json)


if __name__ == '__main__':
    app.run()
