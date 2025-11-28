#  STUDENTS SHOULD ONLY EDIT THE FILE NAME IN LINE 7
import sys
import uio
import utime
import uos
from machine import Pin


# File name of the script to import
file_name = "v02"

SCRIPT_DIRECTORY = "/py_scripts"
CONTEXT_RADIUS = 2
LOG_FILE = "/error_log.txt"
MAX_LOG_BYTES = 12 * 1024

# Add the path to the sys.path
sys.path.append(SCRIPT_DIRECTORY)

# Create a stop pin to stop the main loop
stop_pin = Pin(4, Pin.IN, Pin.PULL_UP)


# Create a callback function to stop the main loop when the stop pin is pressed
def callback(stop_pin):
    raise KeyboardInterrupt("Stop pin button pressed")


# Add an interrupt to the stop pin
stop_pin.irq(trigger=Pin.IRQ_FALLING, handler=callback)

ERROR_GUIDANCE = {
    "IMPORT ERROR": [
        "Raised when the import statement has trouble trying to load a library or module. A common issue is that the module does not exist.",
        "Check that the module/import exists in MicroPython or that you have added the library to the 'lib' folder.",
        "Next step: Confirm the script is stored under /py_scripts or /lib and that the name on line 7 matches the file.",
    ],
    "NAME ERROR": [
        "Raised when a local or global name is not found. This is usually a typo in the name of a variable, method or function.",
        "Check the names of all variables, methods and functions have been typed correctly.",
        "Next step: Compare the highlighted context line with the variable/function definitions to locate the mismatch.",
    ],
    "SYNTAX ERROR": [
        "Raised when the parser encounters a syntax error. This may be caused by a typo in the code.",
        "Check the white space, colons, brackets and other syntax elements are correct in the code.",
        "Next step: Fix the syntax around the highlighted line, then re-run the program.",
    ],
    "TYPE ERROR": [
        "Raised when an operation or function is applied to an object of inappropriate type. The associated value is a string giving details about the type mismatch.",
        "Check you are performing the correct processing for the data type.",
        "Next step: Inspect the variables used on the highlighted line and ensure they have the expected data type.",
    ],
    "VALUE ERROR": [
        "Raised when a built-in operation or function receives an argument that has the right type but an inappropriate value.",
        "Next step: Validate the values being passed to the function on the highlighted line before calling it.",
    ],
    "OS ERROR": [
        "This is a system error catch all.",
        "You may want to check the error code or take this error to your teacher.",
        "Next step: Note the error code, verify any file paths, and retry after checking the hardware connections.",
    ],
    "RUNTIME ERROR": [
        "This is a runtime catch all error.",
        "You may want to check the error code or take this error to your teacher.",
        "Next step: Use the code context and traceback to narrow down what ran just before the crash.",
    ],
    "UNEXPECTED ERROR": [
        "Raised when an error was not specifically handled above.",
        "Next step: Review the code context and traceback to decide which exception type needs its own handler.",
    ],
}


def get_script_path():
    module_path = file_name
    if "/" not in module_path and "." in module_path:
        module_path = module_path.replace(".", "/")
    suffix = "" if module_path.endswith(".py") else ".py"
    return "{}{}{}".format(SCRIPT_DIRECTORY, "/" if not module_path.startswith("/") else "", module_path + suffix)


def build_candidate_paths(filename):
    candidates = []
    if filename and isinstance(filename, str):
        candidates.append(filename)
        if not filename.startswith("/"):
            candidates.append("{}/{}".format(SCRIPT_DIRECTORY, filename.lstrip("/")))
            candidates.append("/{}".format(filename.lstrip("/")))
    unique = []
    for path in candidates:
        if path and path not in unique:
            unique.append(path)
    return unique


def load_source_lines(filename):
    candidates = build_candidate_paths(filename)
    for path in candidates:
        try:
            with open(path, "r") as source_file:
                return source_file.readlines(), path
        except OSError:
            continue
    fallback = filename if filename else None
    return None, fallback


LAUNCHER_FILENAME = __file__ if "__file__" in globals() else None


def get_traceback_location(error):
    current = getattr(error, "__traceback__", None)
    fallback = (None, None)
    while current:
        frame = getattr(current, "tb_frame", None)
        code_obj = getattr(frame, "f_code", None)
        potential_filename = getattr(code_obj, "co_filename", None) if code_obj else None
        if isinstance(potential_filename, str):
            fallback = (potential_filename, current.tb_lineno)
            if not LAUNCHER_FILENAME or potential_filename != LAUNCHER_FILENAME:
                return fallback
        current = current.tb_next
    return fallback


def parse_location_from_args(error):
    args = getattr(error, "args", None)
    if not args:
        return None, None
    for arg in args:
        if isinstance(arg, tuple):
            if len(arg) >= 2 and isinstance(arg[1], int):
                potential_filename = arg[0] if isinstance(arg[0], str) else None
                return potential_filename, arg[1]
            # MicroPython SyntaxError uses (message, (filename, line, column, source))
            if (
                len(arg) >= 2
                and isinstance(arg[0], str)
                and isinstance(arg[1], tuple)
                and len(arg[1]) >= 2
                and isinstance(arg[1][0], str)
                and isinstance(arg[1][1], int)
            ):
                return arg[1][0], arg[1][1]
        if isinstance(arg, int):
            return None, arg
    return None, None


def get_syntax_error_details(error):
    if not isinstance(error, SyntaxError):
        return None, None, None, None
    args = getattr(error, "args", None)
    if not args or len(args) < 2:
        return None, None, None, None
    details = args[1]
    if not isinstance(details, tuple) or len(details) < 4:
        return None, None, None, None
    filename = details[0] if isinstance(details[0], str) else None
    line_no = details[1] if isinstance(details[1], int) else None
    column = details[2] if isinstance(details[2], int) else None
    source_line = details[3] if isinstance(details[3], str) else None
    return filename, line_no, column, source_line


def get_error_location(error):
    tb_filename, tb_line = get_traceback_location(error)
    arg_filename, arg_line = parse_location_from_args(error)
    filename = arg_filename or tb_filename or get_script_path()
    line_no = tb_line or arg_line
    return filename, line_no


def print_code_context(error, context_radius=CONTEXT_RADIUS, override_location=None, trace_frames=None):
    if override_location:
        filename, line_no = override_location
    else:
        filename, line_no = get_error_location(error)
    if line_no is None:
        print("--- Code Context ---")
        print("No line information reported for this exception.")
        return
    resolved_filename = filename
    lines, resolved_path = load_source_lines(resolved_filename)
    fallback_display = False
    if not lines and not resolved_filename:
        resolved_filename = get_script_path()
        lines, resolved_path = load_source_lines(resolved_filename)
    if not lines:
        syntax_filename, syntax_line, syntax_column, syntax_source = get_syntax_error_details(error)
        if syntax_source:
            target_filename = resolved_filename or syntax_filename or "dynamic source"
            target_line = line_no or syntax_line or "?"
            line_label_value = syntax_line or line_no
            if isinstance(line_label_value, int) and line_label_value >= 0:
                line_label = "{:03}".format(line_label_value)
            else:
                line_label = "???"
            prefix = ">> {}: ".format(line_label)
            print("--- Code Context ({}:{}) ---".format(target_filename, target_line))
            print("{}{}".format(prefix, syntax_source.rstrip("\n")))
            if isinstance(syntax_column, int) and syntax_column > 0:
                caret_padding = " " * (len(prefix) + syntax_column - 1)
                print("{}^".format(caret_padding))
            return
        if trace_frames:
            for idx in range(len(trace_frames) - 1, -1, -1):
                alt_filename, alt_line = trace_frames[idx]
                if not alt_filename:
                    continue
                if resolved_filename and alt_filename == resolved_filename:
                    continue
                alt_lines, alt_resolved = load_source_lines(alt_filename)
                if alt_lines:
                    print("--- Code Context ---")
                    print(
                        "Unable to open {}. Showing context from {} instead.".format(
                            resolved_filename or "dynamic source", alt_resolved or alt_filename
                        )
                    )
                    lines = alt_lines
                    resolved_path = alt_resolved or alt_filename
                    if isinstance(alt_line, int) and alt_line > 0:
                        line_no = alt_line
                    fallback_display = True
                    break
        if not lines:
            fallback_path = get_script_path()
            fallback_lines, fallback_resolved = load_source_lines(fallback_path)
            if fallback_lines:
                print("--- Code Context ---")
                print(
                    "Unable to open {}. Showing context from {} instead.".format(
                        resolved_filename or "dynamic source", fallback_path
                    )
                )
                lines = fallback_lines
                resolved_path = fallback_resolved or fallback_path
                fallback_display = True
            else:
                path_to_show = resolved_path or resolved_filename or fallback_path
                print("--- Code Context ---")
                print("Unable to open {} to display source context.".format(path_to_show))
                return
    path_to_show = resolved_path or resolved_filename or get_script_path()
    total_lines = len(lines)
    if total_lines == 0:
        print("--- Code Context ---")
        print("The file {} is empty.".format(path_to_show))
        return
    if line_no < 1 or line_no > total_lines:
        print("--- Code Context ({}:{}) ---".format(path_to_show, line_no))
        print("Reported line {} is outside the range of this file (1-{}).".format(line_no, total_lines))
        return
    start = max(0, line_no - 1 - context_radius)
    end = min(total_lines, line_no - 1 + context_radius + 1)
    print("--- Code Context ({}:{}) ---".format(path_to_show, line_no))
    for idx in range(start, end):
        marker = ">>" if idx == line_no - 1 else "  "
        print("{} {:03}: {}".format(marker, idx + 1, lines[idx].rstrip("\n")))


def list_directory(path):
    try:
        return sorted(uos.listdir(path))
    except OSError:
        return None


def print_available_files():
    locations = [SCRIPT_DIRECTORY, "/lib", "/"]
    print("--- Available Files ---")
    for location in locations:
        entries = list_directory(location)
        if entries is None:
            print("{}: unavailable".format(location))
        elif not entries:
            print("{}: <empty>".format(location))
        else:
            print("{}: {}".format(location, ", ".join(entries)))


def capture_trace_text(error):
    buf = uio.StringIO()
    try:
        sys.print_exception(error, buf)
        return buf.getvalue()
    finally:
        buf.close()


def extract_traceback_frames(trace_text):
    frames = []
    if not trace_text:
        return frames
    for raw_line in trace_text.splitlines():
        line = raw_line.strip()
        if not (line.startswith('File "') and ", line " in line):
            continue
        start = line.find('"') + 1
        end = line.find('"', start)
        if start <= 0 or end <= start:
            continue
        filename = line[start:end]
        line_marker = ", line "
        line_index = line.find(line_marker, end)
        if line_index == -1:
            frames.append((filename, None))
            continue
        line_index += len(line_marker)
        remainder = line[line_index:]
        try:
            line_no = int(remainder.split(',', 1)[0].strip())
        except ValueError:
            line_no = None
        frames.append((filename, line_no))
    return frames


def parse_location_from_trace_text(trace_text):
    frames = extract_traceback_frames(trace_text)
    if frames:
        return frames[-1]
    return None, None


def open_log_file():
    try:
        current_size = None
        try:
            with open(LOG_FILE, "r") as existing:
                existing.seek(0, 2)
                current_size = existing.tell()
        except OSError:
            current_size = 0
        if current_size is not None and current_size > 0:
            return None
        mode = "a"
        if current_size is not None and current_size >= MAX_LOG_BYTES:
            mode = "w"
        return open(LOG_FILE, mode)
    except OSError:
        return None


def log_exception(title, error, trace_text, location_override=None):
    log_handle = open_log_file()
    if not log_handle:
        return
    try:
        timestamp = utime.localtime() if hasattr(utime, "localtime") else None
        stamp = "{}-{}-{} {}:{}:{}".format(
            timestamp[0],
            timestamp[1],
            timestamp[2],
            timestamp[3],
            timestamp[4],
            timestamp[5],
        ) if timestamp else "UNKNOWN-TIME"
        if location_override:
            filename, line_no = location_override
        else:
            filename, line_no = get_error_location(error)
        log_handle.write("==== {} ====".format(stamp))
        log_handle.write("\nType: {}".format(title))
        log_handle.write("\nSource: {}:{}".format(filename or "?", line_no or "?"))
        message = getattr(error, "args", None)
        if message:
            log_handle.write("\nMessage: {}".format(message))
        log_handle.write("\nTraceback:\n{}".format(trace_text))
        log_handle.write("\n\n")
    finally:
        log_handle.close()


def handle_exception(title, error):
    print(title)
    messages = ERROR_GUIDANCE.get(title, ERROR_GUIDANCE.get("UNEXPECTED ERROR", []))
    for line in messages:
        print(line)
    if title == "IMPORT ERROR":
        print_available_files()
    filename, line_no = get_error_location(error)
    trace_text = capture_trace_text(error)
    trace_frames = extract_traceback_frames(trace_text)
    parsed_filename, parsed_line = (trace_frames[-1] if trace_frames else (None, None))
    if parsed_filename or parsed_line:
        use_parsed = False
        if not filename and not line_no:
            use_parsed = True
        elif parsed_filename and parsed_filename not in (None, LAUNCHER_FILENAME) and parsed_filename != filename:
            use_parsed = True
        elif title == "SYNTAX ERROR" and parsed_filename:
            use_parsed = True
        if use_parsed:
            if parsed_filename:
                filename = parsed_filename
            if parsed_line:
                line_no = parsed_line
        else:
            if not filename and parsed_filename:
                filename = parsed_filename
            if not line_no and parsed_line:
                line_no = parsed_line
    if filename or line_no:
        print("Location: {}:{}".format(filename or "unknown", line_no or "?"))
    print("Timestamp: {}".format(utime.localtime() if hasattr(utime, "localtime") else "unknown"))
    print_code_context(error, override_location=(filename, line_no), trace_frames=trace_frames)
    print("--- Traceback ---")
    sys.stdout.write(trace_text)
    log_exception(title, error, trace_text, location_override=(filename, line_no))

# Import the v01.py script and setup exception handling
try:
    __import__(file_name)
except KeyboardInterrupt:
    print("KEYBOARD INTERRUPT")
except ImportError as e:
    handle_exception("IMPORT ERROR", e)
except NameError as e:
    handle_exception("NAME ERROR", e)
except SyntaxError as e:
    handle_exception("SYNTAX ERROR", e)
except TypeError as e:
    handle_exception("TYPE ERROR", e)
except ValueError as e:
    handle_exception("VALUE ERROR", e)
except OSError as e:
    handle_exception("OS ERROR", e)
except RuntimeError as e:
    handle_exception("RUNTIME ERROR", e)
except Exception as e:
    handle_exception("UNEXPECTED ERROR", e)