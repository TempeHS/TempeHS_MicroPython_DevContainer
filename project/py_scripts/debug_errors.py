"""Utility script that triggers specific errors so students can test traceback helpers."""

ERROR_TO_TRIGGER = "name"  # Options: import, name, syntax, type, value, os


def trigger_import_error():
    __import__("not_a_real_module")


def trigger_name_error():
    return undefined_symbol  # noqa: F821 - intentional


def trigger_syntax_error():
    compile("if True print('oops')", "demo_syntax.py", "exec")


def trigger_type_error():
    len(42)


def trigger_value_error():
    int("abc")


def trigger_os_error():
    open("/path/that/does/not/exist/demo.txt", "r")


ERROR_MAP = {
    "import": trigger_import_error,
    "name": trigger_name_error,
    "syntax": trigger_syntax_error,
    "type": trigger_type_error,
    "value": trigger_value_error,
    "os": trigger_os_error,
}


selected = ERROR_MAP.get(ERROR_TO_TRIGGER.lower())
if selected:
    print("Triggering {} error...".format(ERROR_TO_TRIGGER.upper()))
    selected()
else:
    print("Unknown ERROR_TO_TRIGGER '{}'.".format(ERROR_TO_TRIGGER))
    print("Pick one of: {}".format(", ".join(sorted(ERROR_MAP.keys()))))
