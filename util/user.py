import pymongo
from bson.objectid import ObjectId


class User:
    id = None   # Primary Key
    github_access_token = None

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token

    def insert_into_db(self, collection):
        self.id = collection.insert_one({"github_access_token": self.github_access_token}).inserted_id
        return self.id

    @staticmethod
    def find_by_token(access_token, collection):
        result = collection.find_one({"github_access_token": access_token})
        if result is not None:
            obj_id = result["_id"].toString()
            user_obj = User(access_token)
            user_obj.id = obj_id
            return user_obj
        else:
            return None

    @staticmethod
    def find_by_id(obj_id, collection):
        result = collection.find_one({"_id": ObjectId(obj_id)})
        if result is not None:
            access_token = result["github_access_token"]
            user_obj = User(access_token)
            user_obj.id = obj_id
            return user_obj
        else:
            return None
