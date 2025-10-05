import importlib
import pathlib

import psycopg
from base import Dispatcher
from config import DB

dispatchers_dir = pathlib.Path(__file__).parent.parent / "dispatchers"

# Find all dispatcher Python files (skip __init__.py and __pycache__)
dispatcher_files = [
    f.stem for f in dispatchers_dir.glob("*.py")
    if not f.name.startswith("__")
]

with psycopg.connect(DB) as conn:
    for module_name in dispatcher_files:
        try:
            # Import the dispatcher module dynamically
            module = importlib.import_module(f"dispatchers.{module_name}")
            # Get MyCollector and MySender classes
            Collector = getattr(module, "MyCollector", None)
            Sender = getattr(module, "MySender", None)
            if Collector and Sender:
                print(f"Running dispatcher: {module_name}")
                dispatcher = Dispatcher(conn, Collector, Sender)
                dispatcher.send()
            else:
                print(
                    f"Skipping {module_name}: MyCollector or MySender not found.")
        except Exception as e:
            print(f"Error running dispatcher {module_name}: {e}")
