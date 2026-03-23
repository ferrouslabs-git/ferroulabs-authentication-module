"""Tests for auth_config_loader — YAML validation and runtime maps."""
import os
import pytest
import tempfile
import textwrap
from pathlib import Path

from app.auth_usermanagement.services.auth_config_loader import (
    load_and_validate_config,
    AuthConfig,
    AuthConfigError,
    STRUCTURAL_PERMISSIONS,
    reset_auth_config,
    get_auth_config,
)


# ── Helpers ──────────────────────────────────────────────────────

def _write_yaml(tmp_path: Path, content: str) -> str:
    p = tmp_path / "auth_config.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


VALID_YAML = """\
version: "3.0"

layers:
  account:
    enabled: true
    display_name: "Account"
  space:
    enabled: true
    display_name: "Space"

inheritance:
  account_member_space_access: none

roles:
  platform:
    - name: super_admin
      display_name: "Super Admin"
      permissions:
        - platform:configure
        - accounts:manage
        - users:suspend

  account:
    - name: account_owner
      display_name: "Account Owner"
      permissions:
        - account:delete
        - account:read
        - spaces:create
        - members:manage
        - members:invite

    - name: account_admin
      display_name: "Account Admin"
      permissions:
        - account:read
        - spaces:create
        - members:invite

    - name: account_member
      display_name: "Account Member"
      permissions:
        - account:read

  space:
    - name: space_admin
      display_name: "Space Admin"
      permissions:
        - space:delete
        - space:configure
        - space:read
        - members:manage
        - members:invite
        - data:read
        - data:write

    - name: space_member
      display_name: "Space Member"
      permissions:
        - space:read
        - data:read
        - data:write

    - name: space_viewer
      display_name: "Space Viewer"
      permissions:
        - space:read
        - data:read
"""


# ── Happy path ───────────────────────────────────────────────────

def test_valid_config_loads(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert config.version == "3.0"
    assert isinstance(config, AuthConfig)


def test_permission_map_populated(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert "super_admin" in config.permission_map
    assert "platform:configure" in config.permission_map["super_admin"]
    assert "account_owner" in config.permission_map
    assert "account:delete" in config.permission_map["account_owner"]
    assert "space_viewer" in config.permission_map
    assert "data:read" in config.permission_map["space_viewer"]


def test_role_display_names(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert config.role_display_names["super_admin"] == "Super Admin"
    assert config.role_display_names["account_owner"] == "Account Owner"
    assert config.role_display_names["space_viewer"] == "Space Viewer"


def test_layer_config(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert config.is_layer_enabled("platform")
    assert config.is_layer_enabled("account")
    assert config.is_layer_enabled("space")


def test_roles_by_layer(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert len(config.roles_by_layer["platform"]) == 1
    assert len(config.roles_by_layer["account"]) == 3
    assert len(config.roles_by_layer["space"]) == 3


def test_inheritance_config(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    assert config.inheritance_config["account_member_space_access"] == "none"


def test_permissions_for_role(tmp_path):
    path = _write_yaml(tmp_path, VALID_YAML)
    config = load_and_validate_config(path)

    perms = config.permissions_for_role("space_admin")
    assert "data:write" in perms
    assert "space:delete" in perms
    assert config.permissions_for_role("nonexistent") == set()


# ── Validation errors ────────────────────────────────────────────

def test_wrong_version(tmp_path):
    yaml = VALID_YAML.replace('version: "3.0"', 'version: "2.0"')
    path = _write_yaml(tmp_path, yaml)
    with pytest.raises(AuthConfigError, match="Unsupported config version"):
        load_and_validate_config(path)


def test_missing_file():
    with pytest.raises(AuthConfigError, match="Config file not found"):
        load_and_validate_config("/nonexistent/path.yaml")


def test_duplicate_role_name(tmp_path):
    yaml = VALID_YAML + textwrap.dedent("""
    """)
    # Inject a duplicate role name into account layer
    yaml = yaml.replace(
        "    - name: account_member\n",
        "    - name: space_viewer\n",  # duplicate of space layer role
    )
    path = _write_yaml(tmp_path, yaml)
    with pytest.raises(AuthConfigError, match="Duplicate role name"):
        load_and_validate_config(path)


def test_invalid_permission_format(tmp_path):
    yaml = VALID_YAML.replace("- data:read", "- Data:Read")
    path = _write_yaml(tmp_path, yaml)
    with pytest.raises(AuthConfigError, match="doesn't match pattern"):
        load_and_validate_config(path)


def test_disabled_layer_with_roles(tmp_path):
    yaml = VALID_YAML.replace("    enabled: true\n    display_name: \"Space\"",
                               "    enabled: false\n    display_name: \"Space\"")
    path = _write_yaml(tmp_path, yaml)
    with pytest.raises(AuthConfigError, match="disabled but has roles"):
        load_and_validate_config(path)


def test_invalid_inheritance_value(tmp_path):
    yaml = VALID_YAML.replace(
        "account_member_space_access: none",
        "account_member_space_access: invalid_value",
    )
    path = _write_yaml(tmp_path, yaml)
    with pytest.raises(AuthConfigError, match="invalid"):
        load_and_validate_config(path)


# ── Singleton behavior ────────────────────────────────────────────

def test_singleton_caching(tmp_path, monkeypatch):
    path = _write_yaml(tmp_path, VALID_YAML)
    monkeypatch.setenv("AUTH_CONFIG_PATH", path)
    reset_auth_config()

    cfg1 = get_auth_config()
    cfg2 = get_auth_config()
    assert cfg1 is cfg2

    reset_auth_config()


def test_singleton_reset(tmp_path, monkeypatch):
    path = _write_yaml(tmp_path, VALID_YAML)
    monkeypatch.setenv("AUTH_CONFIG_PATH", path)
    reset_auth_config()

    cfg1 = get_auth_config()
    reset_auth_config()
    cfg2 = get_auth_config()
    assert cfg1 is not cfg2

    reset_auth_config()
