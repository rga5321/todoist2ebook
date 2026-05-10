#! /bin/bash

# Execute main.py, passing any arguments using $@
cd /home/appuser/todoist2ebook
exec /home/appuser/todoist2ebook/.venv/bin/python3 main.py "$@"