from flask import Flask, render_template, redirect, url_for, request
import datetime
import urllib.parse

app = Flask(__name__)


@app.route('/submit-places', methods=['GET', 'POST'])
def submit_places():
    if request.method == 'POST':
        url1 = request.form.get('place1')
        url2 = request.form.get('place2')

        # Extract "query" from the URL to build a static iframe (simple solution)
        def extract_query(url):
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query).get('q')
            return query[0] if query else None

        place_query_1 = extract_query(url1)
        place_query_2 = extract_query(url2)

        return render_template(
            'submit_places.html',
            place1=url1,
            place2=url2,
            embed1=place_query_1,
            embed2=place_query_2,
            confirmed=False
        )

    return render_template('submit_places.html', confirmed=False)


@app.route('/confirm-places', methods=['POST'])
def confirm_places():
    # Record the confirmation
    with open("place_confirmations.txt", "a") as f:
        f.write(f"Places confirmed at {datetime.datetime.now()}\n")
    return redirect(url_for('thank_you'))


@app.route('/confirm', methods=['GET'])
def confirm():
    # Render the confirmation page (modifiable via Jinja2)
    return render_template('confirm.html', message="Do you want to confirm this action?")


@app.route('/confirm', methods=['POST'])
def confirm_post():
    # Here you record the confirmation
    with open("confirmation_log.txt", "a") as f:
        f.write(f"Confirmed at {datetime.datetime.now()}\n")

    return redirect(url_for('thank_you'))


@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')


if __name__ == '__main__':
    app.run(debug=True)
