
from datetime import timedelta

from flask import Flask, session

from form_app.config import BaseConfig
from form_app.database import init_db
from form_app.routes import dashboard, admin, auth
from flask_login import LoginManager
from form_app.database import get_db
from shared.database.models import Member

app = Flask(__name__)
app.config.from_object(BaseConfig)

# Set the "Remember Me" cookie to last 1 year (or 10 years, effectively "forever")
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)

init_db(app)


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    db = get_db()
    return db.query(Member).get(int(user_id))


app.register_blueprint(dashboard.bp)
app.register_blueprint(admin.admin_bp)
app.register_blueprint(auth.auth_bp)


@app.route('/logout')
def logout():
    # Removes all data from the session
    session.clear()
    return 'logout!'


if __name__ == '__main__':
    app.run(debug=True)
