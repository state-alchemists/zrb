from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print('=== Routes ===')
for r in app.routes:
    if hasattr(r, 'methods'):
        print(f'{list(r.methods)} {r.path}')

print()
print('=== Test GET /tasks (no auth required) ===')
resp = client.get('/tasks')
print(f'Status: {resp.status_code}, Tasks: {len(resp.json())}')

print()
print('=== Test GET /tasks with filters ===')
resp = client.get('/tasks?status=todo&page=1&page_size=2')
print(f'Status: {resp.status_code}, Tasks: {len(resp.json())}')

print()
print('=== Test POST /tasks without auth ===')
resp = client.post('/tasks', json={'title': 'Test', 'project_id': 1})
print(f'Status: {resp.status_code}, Detail: {resp.json().get("detail", "N/A")}')

print()
print('=== Test POST /tasks with auth ===')
resp = client.post('/tasks', json={'title': 'Test', 'project_id': 1}, headers={'X-API-Key': 'dev-key-alice'})
print(f'Status: {resp.status_code}, Task: {resp.json()}')

print()
print('=== Test PUT /tasks/{id} ===')
resp = client.put('/tasks/1', json={'status': 'done'}, headers={'X-API-Key': 'dev-key-alice'})
print(f'Status: {resp.status_code}, Task status: {resp.json().get("status", "N/A")}')

print()
print('=== Test DELETE /tasks/{id} ===')
new_task = client.post('/tasks', json={'title': 'To Delete', 'project_id': 1}, headers={'X-API-Key': 'dev-key-alice'}).json()
resp = client.delete(f"/tasks/{new_task['id']}", headers={'X-API-Key': 'dev-key-alice'})
print(f'Status: {resp.status_code} (204 expected)')

print()
print('=== Test DELETE 404 ===')
resp = client.delete('/tasks/99999', headers={'X-API-Key': 'dev-key-alice'})
print(f'Status: {resp.status_code}, Detail: {resp.json().get("detail", "N/A")}')
