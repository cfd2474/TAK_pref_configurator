"""XML encoding utilities matching ATAK PreferenceControl.encode/decode."""

import re

# XML 1.0 excludes most control characters in document content.
INVALID_XML_CHARS = re.compile(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD]")

JAVA_CLASS_MAP = {
    "string": "class java.lang.String",
    "boolean": "class java.lang.Boolean",
    "integer": "class java.lang.Integer",
    "float": "class java.lang.Float",
    "long": "class java.lang.Long",
    "set": "class java.util.HashSet",
}


def java_class_for_type(value_type: str) -> str:
    return JAVA_CLASS_MAP.get(value_type, JAVA_CLASS_MAP["string"])


def sanitize_pref_xml(content: str) -> str:
    """Remove invalid XML characters found in some TAK-CIV EUD exports."""
    return INVALID_XML_CHARS.sub("", content)


def encode_value(value: str) -> str:
    """Encode special characters the way ATAK PreferenceControl does."""
    return (
        value.replace('"', "\\u0022")
        .replace("'", "\\u0027")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def decode_value(value: str) -> str:
    """Decode ATAK unicode escape sequences."""
    return (
        value.replace("\\u0022", '"')
        .replace("\\u0027", "'")
        .replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\u0026", "&")
    )


def escape_xml_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
