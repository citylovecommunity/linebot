import dispatchers
import dispatchers.invitation
import psycopg
from base import Dispatcher
from config import DB

with psycopg.connect(DB) as conn:
    dispatcher = Dispatcher(conn, dispatchers.invitation.MyCollector,
                            dispatchers.invitation.MySender)
    dispatcher.run()
