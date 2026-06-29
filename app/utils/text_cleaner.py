import re


_BULLET_CHARS = {
    "\u2022": "-",
    "\u25e6": "-",
    "\u25aa": "-",
    "\u25ab": "-",
    "\u2043": "-",
    "\u2219": "-",
    "\uf0b7": "-",
    "\u00b7": "-",
    "\u25c6": "-",
    "\u25c7": "-",
    "\u2756": "-",
}


def clean_resume_text(text: str) -> str:
    """Normalize extracted resume text without destroying skill symbols."""
    if not text:
        return ""

    for source, replacement in _BULLET_CHARS.items():
        text = text.replace(source, replacement)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
