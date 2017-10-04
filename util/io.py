import requests, time
from jwt import JWT


def download_patch(url, http_auth, pr_id, repo_id):
    response_data = requests.get(url, auth=http_auth)
    if response_data.status_code == 200:
        with open('patches/%s-%s.txt' % (str(pr_id), str(repo_id)), 'wb') as f:
            f.write(response_data.content)
    else:
        print("Error downloading patch: Status Code " + response_data.status_code)


def get_auth_header(installation_id, priv_key):
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