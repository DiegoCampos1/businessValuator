"""Criptografia simetrica das chaves de API dos usuarios.

Usa Fernet (AES-128-CBC + HMAC) com uma master key unica no .env.
A chave so deve ser decifrada em memoria no momento do uso; nunca em logs,
respostas de API ou persistencia em texto plano.
"""

from cryptography.fernet import Fernet


class EncryptionError(Exception):
    pass


class EncryptionService:
    def __init__(self, master_key: str):
        if not master_key:
            raise EncryptionError("MASTER_KEY nao configurada")
        try:
            self._fernet = Fernet(master_key.encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise EncryptionError("MASTER_KEY invalida (deve ser uma Fernet key)") from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise EncryptionError("falha ao decifrar chave") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")


def key_hint(api_key: str) -> str:
    """Mascara a chave exibindo apenas prefixo e sufixo."""
    if len(api_key) <= 8:
        return api_key[:3] + "***"
    return f"{api_key[:3]}...{api_key[-4:]}"
