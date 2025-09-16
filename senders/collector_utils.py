
from psycopg.rows import namedtuple_row


def get_list(conn, state):
    stmt = """
    select * from
    matching where
    current_state = %s;
    """
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_sending',)).fetchall()


def get_notification_list(conn, state, time):
    if time == '24':
        stmt = """
        select * from
        matching where
        current_state = %s
        and now() - last_sent_at between interval '24 hours' and interval '48 hours'
        ;
        """
    elif time == '48':
        stmt = """
        select * from
        matching where
        current_state = %s
        and now() - last_sent_at >= interval '48 hours'
        """
    else:
        raise ValueError('time must be 24 or 48')
    with conn.cursor(row_factory=namedtuple_row) as cur:
        return cur.execute(stmt, (state+'_waiting',)).fetchall()
