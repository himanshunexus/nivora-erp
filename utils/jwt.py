import base64
import hashlib
import hmac
import json
import time


class JWTError(Exception):
    pass


def _b64encode(value):
    encoded = base64.urlsafe_b64encode(value).decode("utf-8")
    return encoded.rstrip("=")


def _b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def encode_token(payload, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def decode_token(token, secret):
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise JWTError("Malformed token.") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _b64decode(signature_segment)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise JWTError("Invalid token signature.")

    payload = json.loads(_b64decode(payload_segment).decode("utf-8"))
    exp = payload.get("exp")
    if exp and exp < int(time.time()):
        raise JWTError("Token expired.")
    return payload
