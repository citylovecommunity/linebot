
import logging
from datetime import timedelta

from flask import Flask, redirect, session, url_for
from flask_login import LoginManager, current_user

from form_app.config import settings
from form_app.database import get_db, init_db
from form_app.routes import admin, auth, dashboard, tasks, webhook
from shared.database.models import Member

app = Flask(__name__)
app.config.from_object(settings)

# Set the "Remember Me" cookie to last 1 year (or 10 years, effectively "forever")
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


init_db(app)


app.register_blueprint(dashboard.bp)
app.register_blueprint(admin.bp)
app.register_blueprint(auth.bp)
app.register_blueprint(webhook.bp)
app.register_blueprint(tasks.bp)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_bp.login'


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    return db.get(Member, int(user_id))


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_bp.dashboard'))
    else:
        return redirect(url_for('auth_bp.login'))


@app.route('/logout')
def logout():
    # Removes all data from the session
    session.clear()
    return 'logout!'


if __name__ == '__main__':
    app.run(debug=True)
