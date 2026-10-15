import json
import unittest

from mcpcross import jwtkit


def make(header, claims, sig=b"sig"):
    return ".".join([jwtkit.b64u(json.dumps(header).encode()), jwtkit.b64u(json.dumps(claims).encode()), jwtkit.b64u(sig)])


class JwtKitTests(unittest.TestCase):
    def test_b64_roundtrip_without_padding(self):
        for n in range(0, 9):
            raw = bytes(range(n))
            enc = jwtkit.b64u(raw)
            self.assertNotIn("=", enc)
            self.assertEqual(jwtkit.b64d(enc), raw)

    def test_header_and_claims_decode(self):
        t = make({"alg": "HS256", "kid": "k1"}, {"sub": "a", "aud": "x"})
        self.assertEqual(jwtkit.header(t), {"alg": "HS256", "kid": "k1"})
        self.assertEqual(jwtkit.claims(t)["sub"], "a")

    def test_flip_signature_bit_changes_only_signature(self):
        t = make({"alg": "HS256"}, {"sub": "a"}, sig=b"\x00" * 32)
        f = jwtkit.flip_signature_bit(t)
        self.assertNotEqual(t, f)
        self.assertEqual(t.split(".")[:2], f.split(".")[:2])
        self.assertEqual(len(jwtkit.b64d(f.split(".")[2])), 32)

    def test_alg_none_has_empty_signature(self):
        t = jwtkit.alg_none(make({"alg": "HS256"}, {"sub": "a"}))
        self.assertEqual(jwtkit.header(t)["alg"], "none")
        self.assertEqual(t.split(".")[2], "")

    def test_strip_kid(self):
        t = jwtkit.strip_kid(make({"alg": "HS256", "kid": "k"}, {"sub": "a"}))
        self.assertNotIn("kid", jwtkit.header(t))


if __name__ == "__main__":
    unittest.main()
