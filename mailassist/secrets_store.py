"""パスワードや API キーを Windows の資格情報マネージャーに保存する。"""

import keyring
from keyring.errors import KeyringError

from . import APP_ID

SMTP_PASSWORD = "smtp_password"
IMAP_PASSWORD = "imap_password"
ANTHROPIC_API_KEY = "anthropic_api_key"


def get_secret(name: str) -> str:
    try:
        return keyring.get_password(APP_ID, name) or ""
    except KeyringError:
        return ""


def set_secret(name: str, value: str) -> None:
    try:
        if value:
            keyring.set_password(APP_ID, name, value)
        else:
            try:
                keyring.delete_password(APP_ID, name)
            except keyring.errors.PasswordDeleteError:
                pass
    except KeyringError as e:
        raise RuntimeError(f"資格情報の保存に失敗しました: {e}") from e
