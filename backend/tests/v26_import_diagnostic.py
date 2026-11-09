"""Redacted import diagnostics shared by CLI and fixture (also when run via -m)."""
from contextlib import contextmanager
import importlib
from pathlib import Path
import traceback

SOURCE = Path(__file__).resolve().parents[2]
DEPENDENCIES = {
    'uvicorn': 'uvicorn', 'psycopg': 'psycopg', 'sqlalchemy': 'SQLAlchemy',
    'fastapi': 'fastapi', 'pydantic': 'pydantic', 'PIL': 'Pillow',
}
ERROR_CLASSES = {'ModuleNotFoundError', 'ImportError', 'OSError', 'RuntimeError',
                 'ValueError', 'TypeError', 'AttributeError', 'AssertionError'}
LAST_IMPORT_FAILURE = None


class DependencyUnavailable(RuntimeError):
    def __init__(self, dependency, error):
        self.safe_details = 'dependency=' + dependency + ' ' + details(error)
        super().__init__('ACCEPTANCE_DEPENDENCY_UNAVAILABLE ' + self.safe_details)


def details(error):
    if isinstance(error, DependencyUnavailable):
        return error.safe_details
    name = type(error).__name__
    fields = ['error_class=' + (name if name in ERROR_CLASSES else 'OtherError')]
    if isinstance(error, ModuleNotFoundError):
        dependency = DEPENDENCIES.get((error.name or '').split('.')[0])
        if dependency:
            fields.append('missing_dependency=' + dependency)
    # Never format exception text, source lines, locals, DSNs or absolute paths.
    for frame in reversed(traceback.extract_tb(error.__traceback__)):
        try:
            path = Path(frame.filename).resolve().relative_to(SOURCE)
        except ValueError:
            continue
        if path.parts[0] == 'backend' and path.suffix == '.py' and (SOURCE / path).is_file():
            fields.append('source=' + path.as_posix() + ':' + str(frame.lineno))
            break
    return ' '.join(fields)


@contextmanager
def capture_import_failure():
    global LAST_IMPORT_FAILURE
    LAST_IMPORT_FAILURE = None
    try:
        yield
    except Exception as error:
        LAST_IMPORT_FAILURE = details(error)
        raise


def check_dependencies():
    # Import compiled Pillow as well: find_spec('PIL') alone misses broken wheels.
    for module in (*DEPENDENCIES.keys(), 'PIL.Image'):
        try:
            importlib.import_module(module)
        except Exception as error:
            # Fixed module/distribution allowlist; omit the original message.
            dependency = DEPENDENCIES[module.split('.')[0]]
            raise DependencyUnavailable(dependency, error) from None


def import_application_graph():
    importlib.import_module('backend.tests.test_v26_identity_postgres')
    importlib.import_module('app.main')
