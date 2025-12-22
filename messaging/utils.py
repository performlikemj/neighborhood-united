import re

DEBUG_TIMESTAMP_SUFFIX_RE = re.compile(
    r"\s+\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z\s*$"
)


def normalize_message_content(content):
    """
    Remove trailing debug timestamp suffixes (e.g. 2025-12-21T13-09-24-658Z)
    that were appended to messages for uniqueness during testing.
    """
    if content is None:
        return ''

    text = str(content)
    stripped = text.strip()
    cleaned = DEBUG_TIMESTAMP_SUFFIX_RE.sub('', stripped)

    if cleaned != stripped:
        cleaned = cleaned.rstrip()
        if cleaned:
            return cleaned

    return stripped
