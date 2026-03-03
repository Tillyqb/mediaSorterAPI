import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

omdb_api_key = '2615867c'
omdb_api_url = 'http://www.omdbapi.com/?apikey=' + omdb_api_key

app = Flask(__name__)

CORS(app)

def fetch_movie_data(title):
    print(f"Fetching data for movie: {title}")
    
    params = {
        's': title,
        'plot': 'short'
    }
    response = requests.get(omdb_api_url, params=params)
    print(response)
    if (response.status_code == 200):
        return response.json()
    else:
        return "No returned data"
    
# movie_list = fetch_movie_data('Dune')

@app.after_request
def add_cors_headers(movie_data):
    movie_data.headers['Access-Control-Allow-Origin'] = '*'
    movie_data.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    movie_data.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    return movie_data

@app.route('/movies', methods=['GET'])
def get_movies():
    title = request.args.get('title', default='Dune', type=str)
    response = fetch_movie_data(title)
    print(response, flush=True)
    movie_data = []
    for movie in response.get('Search', []):
        movie_data.append(movie)
    print(movie_data, flush=True)
    return jsonify(movie_data)

def get_movie():
    title = request.args.get('title', default='Dune', type=str)
    response = fetch_movie_data(title)
    print(response, flush=True)
    return jsonify(response)

if __name__ == '__main__':
    # app.run(debug=True)   # Running in debug mode reloads the server automatically on code changes
    app.run(host='0.0.0.0', port=5000)