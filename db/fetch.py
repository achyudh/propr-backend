import requests, pymongo
from bson.objectid import ObjectId


def form_history(user_id, pr_url):
    feedback_coll = pymongo.MongoClient().pr_database.pr_feedback
    result = feedback_coll.find_one({"user.id": user_id, "pr_url": pr_url})
    del result["user"]
    return result