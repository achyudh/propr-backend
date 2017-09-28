import requests


def download_patch(url, http_auth, pr_id, repo_id):
    response_data = requests.get(url, auth=http_auth)
    if response_data.status_code == 200:
        with open('patches/%s-%s.txt' % (str(pr_id), str(repo_id)), 'wb') as f:
            f.write(response_data.content)
    else:
        print("Error downloading patch: Status Code " + response_data.status_code)