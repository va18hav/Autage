import hashlib
import hmac

def compute_hmac_signature(payload: bytes, secret: str) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

def verify_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    if not signature_header:
        return False

    provided_signature = signature_header.strip()
    if provided_signature.startswith("sha256="):
        provided_signature = provided_signature[len("sha256="):]

    expected_signature = compute_hmac_signature(payload, secret)

    return hmac.compare_digest(expected_signature, provided_signature)
