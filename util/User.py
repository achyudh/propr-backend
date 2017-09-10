class User:
    user_id = None   # Primary Key
    github_access_token = None

    def __init__(self, user_id, github_access_token):
        self.github_access_token = github_access_token

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token