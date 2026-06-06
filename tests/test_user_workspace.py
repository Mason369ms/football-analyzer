from contextlib import contextmanager
import os
import shutil
import unittest
import uuid
from pathlib import Path

from football_sim.user_workspace import normalize_username, workspace_for_user


@contextmanager
def _temp_dir():
    base = Path(os.environ.get("TEST_TMPDIR", Path.cwd() / ".test-tmp"))
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"workspace-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class UserWorkspaceTests(unittest.TestCase):
    def test_normalize_username_uses_safe_ascii_slug(self):
        self.assertEqual(normalize_username(" Alice Smith "), "alice-smith")
        self.assertEqual(normalize_username("Admin_01"), "admin_01")

        with self.assertRaises(ValueError):
            normalize_username("   ")

    def test_workspace_for_user_creates_private_directories(self):
        with _temp_dir() as tmp:
            root = Path(tmp)

            workspace = workspace_for_user(root, "Alice Smith")

            self.assertEqual(workspace.username, "alice-smith")
            self.assertEqual(workspace.data_dir, root / "data" / "users" / "alice-smith")
            self.assertEqual(workspace.reports_dir, root / "reports" / "users" / "alice-smith" / "latest")
            self.assertEqual(workspace.history_db, workspace.data_dir / "history.sqlite3")
            self.assertTrue(workspace.matches_dir.is_dir())
            self.assertTrue(workspace.analyses_dir.is_dir())
            self.assertTrue(workspace.reports_dir.is_dir())
            self.assertTrue(workspace.exports_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
