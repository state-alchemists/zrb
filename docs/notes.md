# Create permission bulk

```json
[
  {"name": "book:create", "description": "create book"},
  {"name": "book:update", "description": "update book"},
  {"name": "book:delete", "description": "delete book"},
  {"name": "book:view", "description": "view book"}
]
```

# Create roles bulk

```json
[
  {
    "name": "librarian",
    "description": "Full access to manage books",
    "permission_names": [
      "book:create",
      "book:update",
      "book:delete",
      "book:view"
    ]
  },
  {
    "name": "assistant-librarian",
    "description": "Can create, update, and view books, but not delete them",
    "permission_names": [
      "book:create",
      "book:update",
      "book:view"
    ]
  },
  {
    "name": "viewer",
    "description": "Can only view books",
    "permission_names": [
      "book:view"
    ]
  }
]
```

# Create user bulk

```json
[
  {
    "username": "john_doe",
    "password": "password123",
    "role_names": [
      "librarian"
    ]
  },
  {
    "username": "jane_smith",
    "password": "securePass!2025",
    "role_names": [
      "assistant-librarian"
    ]
  },
  {
    "username": "alex_viewer",
    "password": "viewOnly@2025",
    "role_names": [
      "viewer"
    ]
  },
  {
    "username": "emily_helper",
    "password": "strongPass$567",
    "role_names": [
      "assistant-librarian",
      "viewer"
    ]
  }
]
```
