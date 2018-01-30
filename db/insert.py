import requests, hashlib, sys, pymongo, datetime
from bson.objectid import ObjectId
from flask import redirect


def moz_feedback(request):
    # Insert feedback into DB
    pr_db = pymongo.MongoClient().pr_database
    del request["action"]
    request["time"] = str(datetime.datetime.now())
    return pr_db.moz_feedback.insert_one(request).inserted_id


def feedback(request):
    # Insert feedback into DB
    pr_db = pymongo.MongoClient().pr_database
    del request["action"]
    return pr_db.pr_feedback.insert_one(request).inserted_id


def feedback_with_participant(request, oauth_token):
    del request["action"]
    pr_db = pymongo.MongoClient().pr_database
    response_user = requests.get("https://api.github.com/user",
                                 headers={'Authorization': 'token %s' % oauth_token}).json()
    request["user"] = {
        "id": hashlib.sha256(str.encode(response_user["login"])).hexdigest(),
        "public_repos": response_user["public_repos"],
        "public_gists": response_user["public_gists"],
        "followers": response_user["followers"],
        "following": response_user["following"],
        "created_at": response_user["created_at"],
        "updated_at": response_user["updated_at"],
        "collaborators": response_user["collaborators"]
    }
    pr_db.pr_feedback.insert_one(request)
    return redirect(request['pr_url'])


def context(full_repo_name, pr_num, http_auth=None, headers=None, code_privacy=False):
    pr_db = pymongo.MongoClient().pr_database
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


def participant_into_feedback(oauth_token, state):
    client = pymongo.MongoClient()
    response_user = requests.get("https://api.github.com/user",
                                 headers={'Authorization': 'token %s' % oauth_token}).json()
    user_info = {
        "id": hashlib.sha256(str.encode(response_user["login"])).hexdigest(),
        "public_repos": response_user["public_repos"],
        "public_gists": response_user["public_gists"],
        "followers": response_user["followers"],
        "following": response_user["following"],
        "created_at": response_user["created_at"],
        "updated_at": response_user["updated_at"],
    }
    feedback_coll = client.pr_database.pr_feedback
    obj_id = ObjectId(state)
    result = feedback_coll.find_one({"_id": obj_id})
    feedback_coll.update_one(
        {"_id": obj_id},
        {"$set": {"user": user_info}}
    )
    if result["pr_url"] is not None:
        return redirect(result["pr_url"])
    else:
        return "DB entry not found", 500


def participant(oauth_token, state):
    client = pymongo.MongoClient()
    response_user = requests.get("https://api.github.com/user",
                                 headers={'Authorization': 'token %s' % oauth_token}).json()
    user_info = {
        "id": hashlib.sha256(str.encode(response_user["login"])).hexdigest(),
        "public_repos": response_user["public_repos"],
        "public_gists": response_user["public_gists"],
        "followers": response_user["followers"],
        "following": response_user["following"],
        "created_at": response_user["created_at"],
        "updated_at": response_user["updated_at"],
    }
    feedback_coll = client.pr_database.pr_feedback
    feedback_coll.insert_one({"_id": ObjectId(state), "user": user_info})
    return user_info["id"]


def feedback_into_participant(request, state):
    client = pymongo.MongoClient()
    feedback_coll = client.pr_database.pr_feedback
    del request["action"]
    del request["state"]
    obj_id = ObjectId(state)
    request["user"] = feedback_coll.find_one({"_id": obj_id})["user"]
    request["_id"] = obj_id
    feedback_coll.replace_one({"_id": obj_id}, request)
