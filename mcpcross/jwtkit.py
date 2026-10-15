"""Tiny helpers to build deliberately broken JWTs for black-box tests (no signing keys needed)."""
import base64
import json


def b64u(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def split(token):
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("not a compact JWS")
    return parts


def header(token):
    return json.loads(b64d(split(token)[0]))


def claims(token):
    return json.loads(b64d(split(token)[1]))


def flip_signature_bit(token):
    """Same header and payload, signature with one bit flipped (re-encoded canonically)."""
    h, p, s = split(token)
    raw = bytearray(b64d(s))
    raw[0] ^= 0x01
    return ".".join((h, p, b64u(bytes(raw))))


def alg_none(token):
    """Header says alg=none and the signature is empty; payload is kept."""
    _, p, _ = split(token)
    hdr = b64u(json.dumps({"alg": "none", "typ": "JWT"}, separators=(",", ":")).encode())
    return hdr + "." + p + "."


def strip_kid(token):
    """Header without the kid member (signature no longer matches, which is fine for rejection tests)."""
    h, p, s = split(token)
    hdr = header(token)
    hdr.pop("kid", None)
    return ".".join((b64u(json.dumps(hdr, separators=(",", ":"), sort_keys=True).encode()), p, s))
