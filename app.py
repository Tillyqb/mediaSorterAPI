import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

omdb_api_key = '2615867c'
omdb_api_url = 'http://www.omdbapi.com/?apikey=' + omdb_api_key
omdb_poster_url = 'https://img.omdbapi.com/?apikey=' + omdb_api_key + '&'
tmdb_api_key = '9f3877175d9ff3ca95cb439ee8a96447'
tmdb_api_url = "https://api.themoviedb.org/3/movie/"

app = Flask(__name__)

CORS(app)

def fetch_movie_data(title):
    """Query TMDb for movies matching *title*.

    Returns the raw JSON response from the "/search/movie" endpoint.  The
    caller previously expected an object with a "Search" key (OMDb style),
    so `get_movies` translates the TMDb "results" list into the same
    structure for downstream code.
    """
    print(f"Fetching data for movie: {title}", flush=True)

    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        'api_key': tmdb_api_key,
        'query': title,
        # optionally: 'page': 1, 'include_adult': False
    }
    response = requests.get(search_url, params=params)
    print(response, flush=True)
    if response.status_code == 200:
        return response.json()
    else:
        print("TMDb search failed", response.status_code, flush=True)
        return {}
    
def fetch_movie_poster_tmdb(imdb_id):
    """Return poster information for a movie given its IMDb ID.

    TMDb requires its own numeric movie ID, so we first call the /find
    endpoint to convert the IMDb ID.  We then request details/images using
    the TMDb ID and return whatever the front end needs (raw JSON here).
    """
    print(f"Fetching poster (TMDb) for IMDb ID: {imdb_id}", flush=True)

    # convert imdb -> tmdb id
    find_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    params = {
        'api_key': tmdb_api_key,
        'external_source': 'imdb_id'
    }
    resp = requests.get(find_url, params=params)
    print("find response", resp.status_code, resp.text, flush=True)
    if resp.status_code != 200:
        return None
    data = resp.json()
    movies = data.get('movie_results') or []
    if not movies:
        print("no TMDb result for", imdb_id, flush=True)
        return None

    tmdb_id = movies[0]['id']
    # now fetch image details; the caller can build the full URL using the
    # poster_path and TMDb configuration (this keeps the API key off the
    # frontend).
    detail_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    resp2 = requests.get(detail_url, params={'api_key': tmdb_api_key})
    print("detail response", resp2.status_code, resp2.text, flush=True)
    if resp2.status_code == 200:
        # return JSON with poster_path etc.
        return resp2.json()
    print("failed detail fetch", resp2.status_code, flush=True)
    return None

# NOTE: removed the unconditional test call that previously ran at import
# time.  Call via the route instead.

# movie_list = fetch_movie_data('Dune')

@app.after_request
def add_cors_headers(movie_data):
    movie_data.headers['Access-Control-Allow-Origin'] = '*'
    movie_data.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    movie_data.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    return movie_data

@app.route('/movies/poster', methods=['GET'])
def fetch_movie_poster():
    imdb_id = request.args.get('imdb_id')
    print(f"HTTP poster request for IMDb ID: {imdb_id}", flush=True)

    # use TMDb backend; front-end can construct full image URL from
    # returned JSON (see fetch_movie_poster_tmdb above).
    info = fetch_movie_poster_tmdb(imdb_id)
    if info is None:
        return "No returned data", 404
    return jsonify(info)
    

@app.route('/movies', methods=['GET'])
def get_movies():
    title = request.args.get('title', default='Dune', type=str)
    response = fetch_movie_data(title)
    print(response, flush=True)

    # TMDb returns a `results` list.  Convert to the familiar OMDb-style
    # list of movies so the frontend doesn't have to change immediately.
    movie_data = []
    for movie in response.get('results', []):
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