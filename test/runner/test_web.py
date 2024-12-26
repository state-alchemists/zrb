import asyncio
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from uvicorn import Config, Server

from zrb.group.group import Group
from zrb.input.int_input import IntInput
from zrb.runner.web_app import create_web_app
from zrb.runner.web_config.config import WebConfig
from zrb.session_state_logger.session_state_logger_factory import session_state_logger
from zrb.task.task import Task


async def run_web_server(app: FastAPI, port: int):
    config = Config(app=app, host="0.0.0.0", port=port, loop="asyncio")
    server = Server(config)
    await server.serve()


class TestRunWebServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_group = Group(name="root")
        math_group = cls.root_group.add_group(Group("math"))
        math_group.add_task(
            Task(
                name="add",
                input=[IntInput(name="first_num"), IntInput(name="second_num")],
                action="{ctx.input.first_num + ctx.input.second_num}",
            )
        )
        geometry_group = math_group.add_group(Group("geometry"))
        geometry_group.add_task(
            Task(
                name="area",
                input=[IntInput(name="w"), IntInput(name="l")],
                action="{ctx.input.w * ctx.input.l}",
            )
        )
        cls.port = 8080
        cls.app = create_web_app(
            cls.root_group,
            WebConfig(
                port=cls.port,
                secret_key="zrb",
                access_token_expire_minutes=30,
                refresh_token_expire_minutes=30,
                access_token_cookie_name="access_token",
                refresh_token_cookie_name="refresh_token",
                enable_auth=False,
                super_admin_username="admin",
                super_admin_password="admin",
                guest_username="guest",
            ),
            session_state_logger,
        )
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        # Start the server in the background
        cls.server_task = cls.loop.create_task(
            run_web_server(app=cls.app, port=cls.port)
        )

    @classmethod
    def tearDownClass(cls):
        # Stop the event loop and server
        cls.server_task.cancel()
        cls.loop.run_until_complete(cls.loop.shutdown_asyncgens())
        cls.loop.close()

    def test_home_page(self):
        with TestClient(self.app) as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("root", response.text)

    def test_ui_home_page(self):
        with TestClient(self.app) as client:
            response = client.get("/ui")
            self.assertEqual(response.status_code, 200)
            self.assertIn("root", response.text)

    def test_static_found(self):
        with TestClient(self.app) as client:
            response = client.get("/static/pico.min.css")
            self.assertEqual(response.status_code, 200)

    def test_static_not_found(self):
        with TestClient(self.app) as client:
            response = client.get("/static/nano.css")
            self.assertEqual(response.status_code, 404)

    def test_ui_group(self):
        with TestClient(self.app) as client:
            response = client.get("/ui/math")
            self.assertEqual(response.status_code, 200)
            self.assertIn("geometry", response.text)
            self.assertIn("add", response.text)

    def test_ui_task(self):
        with TestClient(self.app) as client:
            response = client.get("/ui/math/add")
            self.assertEqual(response.status_code, 200)
            self.assertIn("add", response.text)
            self.assertIn("first_num", response.text)
            self.assertIn("second_num", response.text)
