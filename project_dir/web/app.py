import datetime
import json
from flask_caching import Cache
import concurrent.futures
from flask import Flask, session, url_for, request, render_template, redirect, g
import os
import dbContext
import utils
import pickle

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Load the trained ML pickle file
monday = pickle.load(open('./static/pickle_files/monday_station.pkl', 'rb'))
tuesday = pickle.load(open("./static/pickle_files/tuesday_station.pkl", "rb"))
wednesday = pickle.load(
    open("./static/pickle_files/wednesday_station.pkl", "rb"))
thursday = pickle.load(
    open("./static/pickle_files/thursday_station.pkl", "rb"))
friday = pickle.load(open("./static/pickle_files/friday_station.pkl", "rb"))
saturday = pickle.load(
    open("./static/pickle_files/saturday_station.pkl", "rb"))
sunday = pickle.load(open("./static/pickle_files/sunday_station.pkl", "rb"))


# router to the prediction service
@app.route("/prediction", methods=['GET', 'POST'])
def prediction_model():
    import numpy as np

    # Store the request from JS
    data = request.args.get('post', 0, type=str)
    print(data)
    data = data.split()
    temperature = float(data[0])
    pressure = int(data[1])
    humidity = int(data[2])
    wind_speed = float(data[3])
    date = (data[4])
    d = datetime.datetime.strptime(date, "%Y-%m-%d")
    date = d.strftime("%A")
    minute = (data[5])
    station = int(data[6])
    d = datetime.datetime.strptime(minute, "%H:%M")
    hours = int(d.hour)
    minute = int(d.minute)

    print("Data to be sent to the prediction model ", data)
    print(type(data))
    prediction_input = [[station, temperature,
                         pressure, humidity, wind_speed, hours, minute]]
    if date == "Monday":
        x = monday.predict(prediction_input)
    elif date == "Tuesday":
        x = tuesday.predict(prediction_input)
    elif date == "Wednesday":
        x = wednesday.predict(prediction_input)
    elif date == "Thursday":
        x = thursday.predict(prediction_input)
    elif date == "Friday":
        x = friday.predict(prediction_input)
    elif date == "Saturday":
        x = saturday.predict(prediction_input)
    elif date == "Sunday":
        x = sunday.predict(prediction_input)

    print("Predicted available bikes for selected station is", int(x[0]))

    # Fetch the ML model output and return as JSON to client
    prediction = [int(x[0])]
    return json.dumps(prediction)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session.pop('user', None)
        if dbContext.login(request.form['email'], request.form['password']):
            session['user'] = request.form['email']
            return redirect(url_for('dashboard'))
        else:
            return render_template('index.html', results=False)
    if session.get('from_register_page'):
        return render_template('index.html', from_register_page=True)
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        validation_results = utils.validate_register_information(request.form['firstName'], request.form['lastName'],
                                                                 request.form['email'], request.form['password'],
                                                                 request.form['confirmPassword'])
        if not validation_results.results:
            return render_template('register.html', errors=validation_results.data)

        results = dbContext.register(request.form['firstName'], request.form['lastName'], request.form['email'],
                                     request.form['password'])
        if results[0]:
            session['from_register_page'] = True
            return redirect(url_for('index', from_register_page=True))
        else:
            return render_template('register.html', errors=results[1])
    return render_template('register.html')


@app.route('/searchStation', methods=['GET'])
def search_station():
    try:
        # return "Pew Pew", 404
        data = dbContext.get_station(name=request.args.get('name'))
        if len(data) < 1:
            return "Station not found.", 404
        return json.dumps(data[0])

    except Exception as e:
        return f"Something went wrong. Please try again. {e}", 500


@app.route('/dashboard')
@cache.cached(timeout=300)  # Cache the page for 5 minutes
def dashboard():
    if g.user:
        stations = None
        bikes = None
        weather = None
        current_availability = None
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Retrieve the data using multiple threads
            station_data_future = executor.submit(dbContext.get_station_data)
            availability_data_future = executor.submit(
                dbContext.get_availability_data)
            weather_data_future = executor.submit(dbContext.get_weather_data)
            current_availability_future = executor.submit(
                dbContext.get_stations_availability)

            # Get the results from the futures
            stations = station_data_future.result()
            bikes = availability_data_future.result()
            weather = weather_data_future.result()
            current_availability = current_availability_future.result()

        return render_template('dashboard.html', weather=weather, bikes=bikes, stations=stations,
                               current_availability=json.dumps(current_availability))
    return redirect(url_for('index'))


@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']


@app.template_filter("tojson")
def tojson_filter(value):
    return json.dumps(value)


if __name__ == '__main__':
    app.run(debug=True)
