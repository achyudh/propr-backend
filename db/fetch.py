import requests, pymongo
from bson.objectid import ObjectId


def form_history(user_id, pr_url):
    feedback_coll = pymongo.MongoClient().pr_database.pr_feedback
    result = feedback_coll.find({"user.id": user_id, "pr_url": pr_url}, limit=1, sort=[('$natural', pymongo.DESCENDING)])[0]
    if result is not None:
        del result["user"]
        del result["_id"]
    return result