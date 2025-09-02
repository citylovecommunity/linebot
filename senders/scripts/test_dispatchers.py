import sys

import psycopg
from config import DB
from dispatchers import DISPATCHER_MAP, get_dispatcher

# 只要測試每一個發送出去的內容是否正確
# dispatcher_types = [
#     "invitation",✅
#     "invitation_24",
#     "invitation_48",
#     "liked",✅
#     "liked_24",
#     "liked_48",
#     "goodbye",
#     "rest_r1",✅
#     "rest_r1_24",
#     "rest_r1_48",
#     "rest_r2",✅
#     "rest_r2_24",
#     "rest_r2_48",
#     "rest_r3",
#     "rest_r3_24",
#     "rest_r3_48",
#     "rest_r4",
#     "rest_r4_24",
#     "rest_r4_48",
#     "deal",
#     "no_action_goodbye",
#     "deal_1d_notification",
#     "deal_3hr_notification",
#     "sudden_change_time_notification",
#     "next_month",
#     "change_time",
#     "rest_r1_next_month",
#     "dating_notification",
#     "dating_feedback",
# ]


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python test_dispatchers.py <dispatcher_type> [all|one] [change_state]")
        print("Available dispatcher types:")
        for key in DISPATCHER_MAP.keys():
            print(f"  - {key}")
        print("change_state: true (default) or false")
        sys.exit(1)

    dispatcher_type = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "one"
    change_state_arg = sys.argv[3] if len(sys.argv) > 3 else "true"
    change_state = change_state_arg.lower() == "true"

    with psycopg.connect(DB) as conn:
        dispatcher = get_dispatcher(dispatcher_type, conn)
        print(
            f"Testing dispatcher: {dispatcher_type} (mode: {mode}, change_state: {change_state})")
        if mode == "one":
            dispatcher.send_one(change_state=change_state)
        else:
            dispatcher.send_all(change_state=change_state)


if __name__ == "__main__":
    main()
