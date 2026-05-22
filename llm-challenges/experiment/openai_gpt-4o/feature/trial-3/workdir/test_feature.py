import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

# 1. get_projects
r = client.get('/projects')
print(f'get_projects: status={r.status_code}, n={len(r.json())}')
assert r.status_code == 200 and len(r.json()) >= 2

# 2. filter_by_status
r = client.get('/tasks?status=done')
data = r.json()
print(f'filter_by_status: status={r.status_code}, all_done={all(t["status"]=="done" for t in data)}')
assert r.status_code == 200 and all(t["status"] == "done" for t in data)

# 3. filter_by_assigned_to
r = client.get('/tasks?assigned_to=alice')
data = r.json()
print(f'filter_by_assigned_to: status={r.status_code}, all_alice={all(t["assigned_to"]=="alice" for t in data)}')
assert r.status_code == 200 and all(t["assigned_to"] == "alice" for t in data)

# 4. pagination
r = client.get('/tasks?page=1&page_size=2')
data = r.json()
print(f'pagination: status={r.status_code}, n={len(data)}')
assert r.status_code == 200 and 0 < len(data) <= 2

# 5. auth_required_on_post
r = client.post('/tasks', json={'title': 'Unauth', 'project_id': 1})
print(f'auth_required_on_post: status={r.status_code}')
assert r.status_code in (401, 403)

# 6. post_creates_task
r = client.post('/tasks', json={'title': 'Auth Task', 'project_id': 1, 'priority': 4}, headers={'X-API-Key': 'dev-key-alice'})
print(f'post_creates_task: status={r.status_code}, body={r.json()}')
assert r.status_code in (200, 201)
assert r.json().get('title') == 'Auth Task'
assert r.json().get('id') is not None

# 7. invalid_project_id_404
r = client.post('/tasks', json={'title': 'Bad', 'project_id': 9999}, headers={'X-API-Key': 'dev-key-alice'})
print(f'invalid_project_id_404: status={r.status_code}')
assert r.status_code == 404

# 8. put_partial_update
update_id = r.json().get('id') or 1
r = client.put(f'/tasks/{update_id}', json={'status': 'in_progress'}, headers={'X-API-Key': 'dev-key-alice'})
print(f'put_partial_update: status={r.status_code}, body={r.json()}')
assert r.status_code == 200
assert r.json().get('status') == 'in_progress'

# 9. delete_removes_task
delete_id = update_id
# Re-fetch it to confirm it exists
r = client.get(f'/tasks/{delete_id}')
print(f'  task exists before delete: status={r.status_code}')
r = client.delete(f'/tasks/{delete_id}', headers={'X-API-Key': 'dev-key-alice'})
print(f'delete: status={r.status_code}')
assert r.status_code in (200, 204)
r2 = client.get(f'/tasks/{delete_id}')
print(f'delete_removes_task (post-get): status={r2.status_code}')
assert r2.status_code == 404

print('\n=== ALL CHECKS PASSED ===')
