import argparse
from utils import (
    load_bubble,
    get_list,
    send_bubble_to_sub,
    write_sent_to_db,
)
from config import DB
import psycopg


from bubble_modifiers import BUBBLE_MODIFIER

# 1. 取得本次發送名單
# 2. 包裝泡泡
# 3. 發送
# 4. 修改db狀態


def no_user_id_warning_modify(base_bubble):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('state')
    args = parser.parse_args()

    state = args.state
    base_bubble = load_bubble(state+'.json')
    with psycopg.connect(DB) as conn:
        # 取得符合資格的傳送名單
        list_of_users = get_list(conn, state)
        for row in list_of_users:
            bubble = BUBBLE_MODIFIER[state](row, base_bubble)
            send_bubble_to_sub(row.subject_id, bubble, '本週會員推薦🥰')
            write_sent_to_db(conn, row.id, state)


if __name__ == '__main__':
    main()
