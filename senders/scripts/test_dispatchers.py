import sys

import psycopg
from config import DB
from dispatchers import DISPATCHER_MAP, get_dispatcher


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_dispatchers.py <dispatcher_type> [all|one]")
        print("Available dispatcher types:")
        for key in DISPATCHER_MAP.keys():
            print(f"  - {key}")
        sys.exit(1)

    dispatcher_type = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "one"

    with psycopg.connect(DB) as conn:
        dispatcher = get_dispatcher(dispatcher_type, conn)
        print(f"Testing dispatcher: {dispatcher_type} (mode: {mode})")
        if mode == "one":
            dispatcher.send_one()
        else:
            dispatcher.send_all()


if __name__ == "__main__":
    main()
