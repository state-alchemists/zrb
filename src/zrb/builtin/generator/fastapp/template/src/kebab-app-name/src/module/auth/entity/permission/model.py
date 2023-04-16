from module.auth.entity.permission.repo import PermissionRepo


class PermissionModel():

    def __init__(self, permission_repo: PermissionRepo):
        self.permission_repo = permission_repo

    def get(self):
        return self.permission_repo.get()
