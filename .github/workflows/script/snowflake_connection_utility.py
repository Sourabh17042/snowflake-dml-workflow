import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def get_private_key_from_env() -> bytes:
    """
    Loads and decodes the PEM private key from the environment.
    Supports both encrypted and unencrypted keys.
    """
    private_key_pem = os.getenv("SNF_USER_PRIVATE_KEY")
    private_key_password = os.getenv("SNF_USER_PRIVATE_KEY_PASSWORD")

    if not private_key_pem:
        raise ValueError("❌ 'SNF_USER_PRIVATE_KEY' environment variable is not set.")

    if "\\n" in private_key_pem:
        private_key_pem = private_key_pem.replace("\\n", "\n")

    private_key_bytes = private_key_pem.encode("utf-8")
    private_key_password_bytes = private_key_password.encode("utf-8") if private_key_password else None

    try:
        p_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=private_key_password_bytes,
            backend=default_backend()
        )

        private_key_der = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        return private_key_der

    except Exception as e:
        raise RuntimeError(f"❌ Failed to load private key: {e}")