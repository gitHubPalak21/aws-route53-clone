import re


def normalize_email(value: str) -> str:
    """Validate common ASCII login addresses, including the demo's .local domain.

    EmailStr rejects .local; these mock identities do not require DNS delivery.
    Quoted local parts and internationalized addresses are outside this demo.
    """
    email = value.strip().lower()
    local, separator, domain = email.partition("@")
    labels = domain.split(".")
    if (
        not separator
        or len(email) > 320
        or not 1 <= len(local) <= 64
        or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or len(domain) > 253
        or len(labels) < 2
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
    ):
        raise ValueError("Enter a valid email address")
    return email
