import os

from locust import HttpUser, between, task

access_token_cookie_key = os.getenv(
    "PUBLIC_AUTH_ACCESS_TOKEN_COOKIE_KEY", "access_token"
)
admin_username = os.getenv("APP_AUTH_ADMIN_USERNAME", "root")
admin_password = os.getenv("APP_AUTH_ADMIN_PASSWORD", "toor")


class QuickstartUser(HttpUser):
    wait_time = between(1, 5)

    @task(2)
    def homepage(self):
        self.client.get("/")

    @task
    def permissions(self):
        self.client.get("/api/v1/auth/permissions")

    def on_start(self):
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={"identity": admin_username, "password": admin_password},
        )
        login_response_json = login_response.json()
        access_token = login_response_json.get("access_token")
        self.client.cookies.set(access_token_cookie_key, access_token)
