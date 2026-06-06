from contextlib import contextmanager
import os
import shutil
import unittest
import uuid
from pathlib import Path

from football_sim.auth import AuthStore, hash_password, verify_password


@contextmanager
def _temp_dir():
    base = Path(os.environ.get("TEST_TMPDIR", Path.cwd() / ".test-tmp"))
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"auth-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class AuthStoreTests(unittest.TestCase):
    def test_password_hash_verifies_only_matching_password(self):
        encoded = hash_password("secret-password")

        self.assertTrue(verify_password("secret-password", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))

    def test_bootstrap_admin_creates_enabled_admin(self):
        with _temp_dir() as tmp:
            store = AuthStore(Path(tmp) / "app_football.sqlite3")

            store.bootstrap_admin("Admin", "secret")

            user = store.authenticate("admin", "secret")
            self.assertIsNotNone(user)
            self.assertEqual(user.username, "admin")
            self.assertTrue(user.is_admin)
            self.assertTrue(user.is_enabled)
            self.assertIsNone(store.authenticate("admin", "wrong"))

    def test_session_lifecycle(self):
        with _temp_dir() as tmp:
            store = AuthStore(Path(tmp) / "app_football.sqlite3")
            store.create_user("alice", "secret")

            token = store.create_session("alice")
            user = store.get_session_user(token)

            self.assertIsNotNone(user)
            self.assertEqual(user.username, "alice")

            store.delete_session(token)

            self.assertIsNone(store.get_session_user(token))


if __name__ == "__main__":
    unittest.main()
