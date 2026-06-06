from contextlib import contextmanager
import io
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

from fastapi.testclient import TestClient

from football_sim.fastapi_app import create_fastapi_app, _render_login_page


@contextmanager
def _temp_dir():
    base = Path(os.environ.get("TEST_TMPDIR", Path.cwd() / ".test-tmp"))
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"fastapi-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class FastApiMultiUserTests(unittest.TestCase):
    def make_client(self, root: Path) -> TestClient:
        env = {
            "FOOTBALL_ADMIN_USER": "admin",
            "FOOTBALL_ADMIN_PASSWORD": "secret",
        }
        patcher = patch.dict(os.environ, env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        app = create_fastapi_app(root / "reports" / "latest", root)
        return TestClient(app)

    def login(self, client: TestClient):
        return client.post(
            "/login",
            data={"username": "admin", "password": "secret"},
            follow_redirects=False,
        )

    def test_unauthenticated_dashboard_shows_directly(self):
        with _temp_dir() as tmp:
            client = self.make_client(Path(tmp))

            def load_model(data_dir=None):
                return object()

            with (
                patch("football_sim.fastapi_app.load_dashboard_model", side_effect=load_model),
                patch("football_sim.fastapi_app.render_dashboard_html", return_value="<html><body>Football Dashboard</body></html>"),
            ):
                response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Football Dashboard", response.text)

    def test_api_returns_data_without_auth(self):
        with _temp_dir() as tmp:
            client = self.make_client(Path(tmp))

            response = client.get("/api/config")

        self.assertEqual(response.status_code, 200)

    def test_login_sets_session_cookie(self):
        with _temp_dir() as tmp:
            client = self.make_client(Path(tmp))

            response = self.login(client)

        self.assertEqual(response.status_code, 303)
        self.assertIn("football_session=", response.headers["set-cookie"])

    def test_login_page_uses_polished_chinese_layout(self):
        page = _render_login_page()

        self.assertIn("足球赛事分析系统", page)
        self.assertIn("账号登录", page)
        self.assertIn('class="login-shell"', page)
        self.assertIn('class="register-link"', page)
        self.assertIn('href="/register"', page)
        self.assertNotIn("admin / admin", page)
        self.assertNotIn("FOOTBALL_ADMIN_PASSWORD", page)
        self.assertNotIn("<h1>Login</h1>", page)

    def test_registration_page_is_available_without_default_password_notice(self):
        with _temp_dir() as tmp:
            client = self.make_client(Path(tmp))

            response = client.get("/register")

        self.assertEqual(response.status_code, 200)
        self.assertIn('action="/register"', response.text)
        self.assertIn('name="username"', response.text)
        self.assertIn('name="password"', response.text)
        self.assertNotIn("admin / admin", response.text)
        self.assertNotIn("FOOTBALL_ADMIN_PASSWORD", response.text)

    def test_default_admin_password_is_not_printed_when_bootstrapping(self):
        with _temp_dir() as tmp:
            env = {
                key: value
                for key, value in os.environ.items()
                if key not in {"FOOTBALL_ADMIN_USER", "FOOTBALL_ADMIN_PASSWORD"}
            }
            output = io.StringIO()

            with patch.dict(os.environ, env, clear=True), redirect_stdout(output):
                create_fastapi_app(Path(tmp) / "reports" / "latest", Path(tmp))

        self.assertNotIn("admin/admin", output.getvalue())
        self.assertNotIn("FOOTBALL_ADMIN_PASSWORD", output.getvalue())

    def test_dashboard_always_uses_default_workspace(self):
        with _temp_dir() as tmp:
            root = Path(tmp)
            client = self.make_client(root)
            seen = {}

            def load_model(data_dir=None):
                seen["data_dir"] = Path(data_dir) if data_dir else None
                return object()

            with (
                patch("football_sim.fastapi_app.load_dashboard_model", side_effect=load_model),
                patch("football_sim.fastapi_app.render_dashboard_html", return_value="<html><body></body></html>"),
            ):
                dashboard_response = client.get("/")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(seen["data_dir"], root / "data" / "users" / "default")

    def test_duplicate_registration_returns_conflict(self):
        with _temp_dir() as tmp:
            client = self.make_client(Path(tmp))

            first = client.post(
                "/register",
                data={"username": "alice", "password": "secret123"},
                follow_redirects=False,
            )
            second = client.post(
                "/register",
                data={"username": "alice", "password": "other-secret"},
                follow_redirects=False,
            )

        self.assertEqual(first.status_code, 303)
        self.assertEqual(second.status_code, 409)

    def test_dashboard_uses_default_workspace(self):
        with _temp_dir() as tmp:
            root = Path(tmp)
            client = self.make_client(root)
            seen = {}

            def load_model(data_dir=None):
                seen["data_dir"] = Path(data_dir) if data_dir else None
                return object()

            with (
                patch("football_sim.fastapi_app.load_dashboard_model", side_effect=load_model),
                patch("football_sim.fastapi_app.render_dashboard_html", return_value="<html><body></body></html>"),
            ):
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["data_dir"], root / "data" / "users" / "default")


if __name__ == "__main__":
    unittest.main()
