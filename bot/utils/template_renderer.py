"""
Safe placeholder substitution for admin-editable message templates.
Deliberately NOT str.format() — an admin free-typing a message in the
Telegram panel might type a literal '{' or '}' by accident (or copy text
that has one), and str.format() would crash the whole handler on that.
This only ever replaces the known {placeholder} tokens we pass in and
leaves everything else in the admin's text completely untouched.
"""


def render_template(template: str, **values: str) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value))
    return result
