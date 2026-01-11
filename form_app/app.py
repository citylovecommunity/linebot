
from datetime import datetime
from config import BaseConfig
from database import init_db
from flask import Flask, session, redirect, url_for
from routes.choose_restaurant import restaurant_bp
import routes
import routes.dashboard
import routes.show_confirmation

app = Flask(__name__)
app.config.from_object(BaseConfig)


init_db(app)


app.register_blueprint(routes.dashboard.bp)
app.register_blueprint(routes.show_confirmation.bp)
app.register_blueprint(restaurant_bp)


@app.route('/logout')
def logout():
    # Removes all data from the session
    session.clear()
    return 'logout!'


@app.template_filter('smart_date')
def smart_date_filter(value):
    if not value:
        return ""

    # If the value is already a string (e.g. "Tue, 13 Jan 2026..."), we need to parse it into a real date object first
    if isinstance(value, str):
        try:
            # parsing the format "Tue, 13 Jan 2026 00:00:00 GMT"
            # If your strings are consistent, use strptime:
            date_obj = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            # Fallback if format is different
            return value
    else:
        # It's already a datetime object
        date_obj = value

    # Format: "2026-01-13 (Tue)"
    # %Y = Year, %m = Month, %d = Day, %a = Short Weekday (Mon/Tue)
    return date_obj.strftime('%Y-%m-%d (%a)')


if __name__ == '__main__':
    app.run(debug=True)
