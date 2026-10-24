"""A deliberately tiny module used by examples/sample-shift.

The shift recorded in this directory is the work of replacing the ascii-only
regex below with a character-class check that keeps unicode letters while still
collapsing separator runs and trimming the ends.
"""


def slugify(text: str) -> str:
    """Turn a title into a url slug.

    Letters and digits survive (including CJK); every run of other characters
    becomes a single hyphen; leading and trailing hyphens are dropped.
    """
    out: list[str] = []
    pending_sep = False
    for ch in text.strip().lower():
        if ch.isalnum():
            if pending_sep and out:
                out.append("-")
            pending_sep = False
            out.append(ch)
        else:
            pending_sep = True
    return "".join(out)
