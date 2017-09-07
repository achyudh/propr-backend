from flask import Flask, request, abort
from requests.auth import HTTPBasicAuth
import requests, json, urllib, pymongo

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():
    http_auth = HTTPBasicAuth('prfeedback', 'rosetta11')
    if request.method == 'POST':
        if request.json["action"] == "closed":
            parsed_json = request.json
            pr_num = parsed_json["pull_request"]["number"]
            pr_id = parsed_json["pull_request"]["id"]
            repo_id = parsed_json["pull_request"]["base"]["repo"]["id"]

            # Only part of the URL is encoded: the owner and repo name
            encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["base"]["repo"]["full_name"])
            feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/index.html?url=%s&prid=%s&repoid=%s&prnum=%s" % (encoded_url, pr_id, repo_id, pr_num)

            # Send POST request to comment on the PR with feedback link
            pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
            pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], pr_num)
            requests.post(pr_comment_url, data=pr_comment_payload,auth=http_auth)
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
            return '', 200
    else:
        abort(400)


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


if __name__ == '__main__':
    app.run()
