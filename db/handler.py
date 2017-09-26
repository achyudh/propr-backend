import requests, hashlib, sys


def insert(request, pr_db, full_repo_name, pr_num, http_auth=None, headers=None, code_privacy=False):
    # Insert feedback into DB
    del request.json["action"]
    ret_val = pr_db.pr_feedback.insert_one(request.json).inserted_id

    # Insert PR info into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    response_json['_id'] = hashlib.sha256(str.encode(str(response_json))).hexdigest()
    try:
        pr_db.pr_info.insert_one(response_json)
    except Exception as e:
        print("IGNORING" + str(e), file=sys.stderr)

    # Insert commits into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/commits' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    for commit_json in response_json:
        commit_json['_id'] = hashlib.sha256(str.encode(str(commit_json))).hexdigest()
    if len(response_json) > 0:
        try:
            pr_db.pr_commits.insert_many(response_json, ordered=False)
        except Exception as e:
            print("IGNORING" + str(e), file=sys.stderr)

    # Insert PR comments into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/comments' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    for comment_json in response_json:
        comment_json['_id'] = hashlib.sha256(str.encode(str(comment_json))).hexdigest()
    if len(response_json) > 0:
        try:
            pr_db.pr_comments.insert_many(response_json, ordered=False)
        except Exception as e:
            print("IGNORING" + str(e), file=sys.stderr)

    # Insert PR reviews into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/reviews' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    for comment_json in response_json:
        comment_json['_id'] = hashlib.sha256(str.encode(str(comment_json))).hexdigest()
    if len(response_json) > 0:
        try:
            pr_db.pr_reviews.insert_many(response_json, ordered=False)
        except Exception as e:
            print("IGNORING" + str(e), file=sys.stderr)

    # Insert issue comments into DB
    request_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (full_repo_name, pr_num)
    if headers is not None:
        response_json = requests.get(request_url, headers=headers).json()
    else:
        response_json = requests.get(request_url, auth=http_auth).json()
    for comment_json in response_json:
        comment_json['_id'] = hashlib.sha256(str.encode(str(comment_json))).hexdigest()
    if len(response_json) > 0:
        try:
            pr_db.issue_comments.insert_many(response_json, ordered=False)
        except Exception as e:
            print("IGNORING" + str(e), file=sys.stderr)

    # Insert patch and files into DB
    request_url = 'https://api.github.com/repos/%s/pulls/%s/files' % (full_repo_name, pr_num)
    if not code_privacy:
        if headers is not None:
            response_json = requests.get(request_url, headers=headers).json()
        else:
            response_json = requests.get(request_url, auth=http_auth).json()
        for file_json in response_json:
            file_json['_id'] = hashlib.sha256(str.encode(str(file_json))).hexdigest()
        if len(response_json) > 0:
            try:
                pr_db.pr_files.insert_many(response_json, ordered=False)
            except Exception as e:
                print("IGNORING" + str(e), file=sys.stderr)
    return ret_val
