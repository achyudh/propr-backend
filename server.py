from flask import Flask, request, abort, redirect, session, g
from requests.auth import HTTPBasicAuth
import requests, json, urllib, pymongo, sys
from flask.ext.github import GitHub
from util import User

app = Flask(__name__)
with open("config.json", 'r') as config_file:
    client_config = json.load(config_file)
app.config['GITHUB_CLIENT_ID'] = client_config['GITHUB_CLIENT_ID']
app.config['GITHUB_CLIENT_SECRET'] = client_config['GITHUB_CLIENT_SECRET']
github = GitHub(app)


@app.route('/login')
def login():
    if session.get('user_id', None) is None:
        return github.authorize(scope="user,repo")
    else:
        return 'User already logged in', 200


@app.route('/callback')
@github.authorized_handler
def authorized(oauth_token):
    if oauth_token is None:
        return redirect("http://dutiap.st.ewi.tudelft.nl:60001/nextsteps.html?success=False")
    user = get_user_with_token(github_access_token=oauth_token)
    if user is None:
        user = User(oauth_token)
        # Add user to DB if not already present
    user.github_access_token = oauth_token
    session['user_id'] = user.id
    return redirect("http://dutiap.st.ewi.tudelft.nl:60001/nextsteps.html?success=True")


@app.route('/webhook', methods=['POST'])
def webhook():
    http_auth = HTTPBasicAuth('prfeedback', 'rosetta11')
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
            isPrivateRepo = request.json["pull_request"]["base"]["repo"]["private"]
            pr_num = parsed_json["pull_request"]["number"]
            pr_id = parsed_json["pull_request"]["id"]
            repo_id = parsed_json["pull_request"]["base"]["repo"]["id"]

            # Only part of the repo URL is encoded: the owner and repo name
            encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["base"]["repo"]["full_name"])
            # This is the entire URL of the PR to which the user iis redirected to once the form is filled
            encoded_return_url = urllib.parse.quote_plus(parsed_json["pull_request"]["html_url"])
            feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/feedback.html?returnurl=%s&url=%s&prid=%s&repoid=%s&prnum=%s&private=%s" % (encoded_return_url, encoded_url, pr_id, repo_id, pr_num, isPrivateRepo)

            # Send POST request to comment on the PR with feedback link
            pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
            pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], pr_num)
            requests.post(pr_comment_url, data=pr_comment_payload,auth=http_auth)
            if not isPrivateRepo:
                download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
            return '', 200

        elif request.json["action"] == "submit":
            client = pymongo.MongoClient()
            pr_db = client.pr_database
            pr_num = request.json["pr_num"]
            full_repo_name = request.json["full_repo_name"]

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
            if not request.json["code_privacy"]:
                request_url = 'https://api.github.com/repos/%s/pulls/%s/files' % (full_repo_name, pr_num)
                response_json = requests.get(request_url, auth=http_auth).json()
                if len(response_json) > 0:
                    pr_db.pr_files.insert_many(response_json)
                return '', 200
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
    if 'user_id' in session:
        g.user = get_user_with_id(session['user_id'])


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


def get_user_with_token(github_access_token):
    # TODO user = User.query.filter_by(github_access_token=access_token).first()
    return None


def get_user_with_id(user_id):
    # TODO user = User.query.get(session['user_id'])
    return None


if __name__ == '__main__':
    app.run()
