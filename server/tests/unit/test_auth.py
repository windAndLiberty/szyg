"""
Unit tests for szyg.auth — JWT + SQLite user management.
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# We need to patch DB_PATH before importing auth, so we use a fixture approach
# that patches at the module level during tests.


@pytest.fixture(autouse=True)
def isolated_auth_db(tmp_path: Path):
    """Patch auth module to use an isolated SQLite DB per test."""
    db_path = str(tmp_path / "test_auth.db")
    with patch("szyg.auth.DB_PATH", db_path):
        # Re-init the DB with the patched path
        import szyg.auth as auth_mod
        auth_mod.DB_PATH = db_path
        auth_mod._init_db()
        auth_mod._default_admin()
        yield auth_mod


class TestPasswordHashing:
    def test_hash_returns_pbkdf2_format(self, isolated_auth_db):
        auth = isolated_auth_db
        hashed = auth._hash_pw("mypassword")
        assert hashed.startswith("pbkdf2:sha256:600000:")
        parts = hashed.split(":")
        assert len(parts) == 5

    def test_hash_with_explicit_salt(self, isolated_auth_db):
        auth = isolated_auth_db
        h1 = auth._hash_pw("pass", salt="fixed_salt")
        h2 = auth._hash_pw("pass", salt="fixed_salt")
        assert h1 == h2

    def test_different_salts_produce_different_hashes(self, isolated_auth_db):
        auth = isolated_auth_db
        h1 = auth._hash_pw("pass", salt="salt_a")
        h2 = auth._hash_pw("pass", salt="salt_b")
        assert h1 != h2

    def test_verify_correct_password(self, isolated_auth_db):
        auth = isolated_auth_db
        hashed = auth._hash_pw("correct")
        assert auth._verify_pw("correct", hashed) is True

    def test_verify_wrong_password(self, isolated_auth_db):
        auth = isolated_auth_db
        hashed = auth._hash_pw("correct")
        assert auth._verify_pw("wrong", hashed) is False

    def test_verify_malformed_hash_returns_false(self, isolated_auth_db):
        auth = isolated_auth_db
        assert auth._verify_pw("anything", "not_a_valid_hash") is False

    def test_verify_empty_hash_returns_false(self, isolated_auth_db):
        auth = isolated_auth_db
        assert auth._verify_pw("pass", "") is False


class TestDefaultAdmin:
    def test_default_admin_created(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.get_user_by_username("admin")
        assert user is not None
        assert user.username == "admin"
        assert user.role == "admin"

    def test_default_admin_password(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.get_user_by_username("admin")
        assert auth._verify_pw("admin123", user.hashed_password) is True


class TestAccessToken:
    def test_create_and_decode_token(self, isolated_auth_db):
        auth = isolated_auth_db
        token = auth.create_access_token({"sub": "1", "username": "testuser"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_claims(self, isolated_auth_db):
        auth = isolated_auth_db
        from jose import jwt
        token = auth.create_access_token({"sub": "42", "username": "alice"})
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert "exp" in payload


class TestAuthenticate:
    def test_successful_login(self, isolated_auth_db):
        auth = isolated_auth_db
        result = auth.authenticate("admin", "admin123")
        assert result is not None
        assert result.access_token
        assert result.user.username == "admin"

    def test_wrong_password(self, isolated_auth_db):
        auth = isolated_auth_db
        result = auth.authenticate("admin", "wrong_pass")
        assert result is None

    def test_nonexistent_user(self, isolated_auth_db):
        auth = isolated_auth_db
        result = auth.authenticate("nobody", "pass")
        assert result is None

    def test_inactive_user_cannot_login(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("inactive_user", "pass123", role="user")
        auth.toggle_user_active(user.id)
        result = auth.authenticate("inactive_user", "pass123")
        assert result is None


class TestGetCurrentUser:
    def test_valid_token(self, isolated_auth_db):
        auth = isolated_auth_db
        token_resp = auth.authenticate("admin", "admin123")
        user = auth.get_current_user(token_resp.access_token)
        assert user is not None
        assert user.username == "admin"

    def test_invalid_token(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.get_current_user("invalid.jwt.token")
        assert user is None

    def test_expired_token_returns_none(self, isolated_auth_db):
        auth = isolated_auth_db
        from datetime import datetime, timedelta
        from jose import jwt
        expired_data = {"sub": "1", "username": "admin", "exp": datetime(2020, 1, 1)}
        token = jwt.encode(expired_data, auth.SECRET_KEY, algorithm=auth.ALGORITHM)
        user = auth.get_current_user(token)
        assert user is None


class TestUserCRUD:
    def test_create_user(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("newuser", "password", role="user", email="new@test.com")
        assert user is not None
        assert user.username == "newuser"
        assert user.role == "user"
        assert user.email == "new@test.com"

    def test_create_duplicate_username(self, isolated_auth_db):
        auth = isolated_auth_db
        auth.create_user("dup", "pass1")
        result = auth.create_user("dup", "pass2")
        assert result is None

    def test_list_users(self, isolated_auth_db):
        auth = isolated_auth_db
        users = auth.list_users()
        assert len(users) >= 1  # At least admin
        assert any(u.username == "admin" for u in users)

    def test_get_user_by_id(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("byid", "pass")
        fetched = auth.get_user_by_id(user.id)
        assert fetched is not None
        assert fetched.username == "byid"

    def test_get_user_by_id_nonexistent(self, isolated_auth_db):
        auth = isolated_auth_db
        assert auth.get_user_by_id(99999) is None

    def test_update_user_email(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("updatable", "pass")
        updated = auth.update_user(user.id, email="updated@test.com")
        assert updated.email == "updated@test.com"

    def test_update_user_role(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("rolechange", "pass")
        updated = auth.update_user(user.id, role="admin")
        assert updated.role == "admin"

    def test_delete_user(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("deleteme", "pass")
        assert auth.delete_user(user.id) is True
        assert auth.get_user_by_id(user.id) is None

    def test_delete_nonexistent(self, isolated_auth_db):
        auth = isolated_auth_db
        assert auth.delete_user(99999) is False

    def test_toggle_user_active(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("toggleme", "pass")
        assert user.is_active is True
        toggled = auth.toggle_user_active(user.id)
        assert toggled.is_active is False
        toggled_back = auth.toggle_user_active(user.id)
        assert toggled_back.is_active is True

    def test_toggle_nonexistent(self, isolated_auth_db):
        auth = isolated_auth_db
        assert auth.toggle_user_active(99999) is None

    def test_create_user_with_oem_id(self, isolated_auth_db):
        auth = isolated_auth_db
        user = auth.create_user("oem_user", "pass", oem_id="oem_123")
        assert user.oem_id == "oem_123"
