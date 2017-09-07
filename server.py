from flask import Flask, request, abort
from requests.auth import HTTPBasicAuth
import requests, json, urllib, pymongo

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():

    if request.method == 'POST':
        if request.json["action"] == "closed":
            parsed_json = request.json
            http_auth = HTTPBasicAuth('prfeedback', 'rosetta11')
            pr_id = parsed_json["pull_request"]["id"]
            repo_id = parsed_json["pull_request"]["base"]["repo"]["id"]
            encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["html_url"])
            feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/index.html?url=%s&prid=%s&repoid=%s" % (encoded_url, pr_id, repo_id)
            pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
            pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], parsed_json["pull_request"]["number"])
            requests.post(pr_comment_url, data=pr_comment_payload,auth=http_auth)
            download_patch(parsed_json["pull_request"]["patch_url"], http_auth, pr_id, repo_id)
            return '', 200
        elif request.json["action"] == "submit":
            client = pymongo.MongoClient()
            pr_db = db = client.pr_database
            collection = pr_db.pr_feedback
            posts = pr_db.posts
            insert_result = posts.insert_one(request.json)
            if posts.find_one({"_id": insert_result.inserted_id}) is not None:
                return '', 200
            else:
                return 'ERROR: DB Insert Failed!', 500
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
