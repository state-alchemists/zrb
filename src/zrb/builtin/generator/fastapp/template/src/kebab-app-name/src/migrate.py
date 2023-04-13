from module.auth import migrate_auth


def migrate():
    migrate_auth()


if __name__ == '__main__':
    migrate()
