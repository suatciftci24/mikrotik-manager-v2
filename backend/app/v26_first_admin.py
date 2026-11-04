"""Owner TTY entry point for explicit V2.6 004/009 migration + first admin."""
from app.first_admin import main

if __name__ == '__main__':
    raise SystemExit(main(v26=True))
