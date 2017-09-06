from flask import Flask, request, abort
from requests.auth import HTTPBasicAuth
import requests, json, urllib

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST' and request.json["action"] == "closed":
        parsed_json = request.json
        http_auth = HTTPBasicAuth('prfeedback', 'rosetta11')
        encoded_url = urllib.parse.quote_plus(parsed_json["pull_request"]["html_url"])
        feedback_url = "http:/dutiap.st.ewi.tudelft.nl:60001/index.html?url=" + encoded_url
        pr_comment_payload = json.dumps({"body": "Please provide your PR feedback [here](%s). " % feedback_url})
        pr_comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (parsed_json["pull_request"]["base"]["repo"]["full_name"], parsed_json["pull_request"]["number"])
        requests.post(pr_comment_url, data=pr_comment_payload,auth=http_auth)
        download_patch(parsed_json["pull_request"]["patch_url"], http_auth, parsed_json["pull_request"]["id"], parsed_json["pull_request"]["base"]["repo"]["id"])
        return "OK"
    else:
        abort(400)


def download_patch(url, http_auth, pr_id, repo_id):
    response_data = requests.get(url, auth=http_auth)
    if response_data.status_code == 200:
        with open('patches/%s-%s.txt' % (pr_id, repo_id), 'wb') as f:
            f.write(response_data.content)
    else:
        print("Error downloading patch: Status Code " + response_data.status_code)


if __name__ == '__main__':
    app.run()
