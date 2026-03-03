import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

omdb_api_key = '2615867c'
omdb_api_url = 'http://www.omdbapi.com/?apikey=' + omdb_api_key
omdb_poster_url = 'https://img.omdbapi.com/?apikey=' + omdb_api_key + '&'
tmdb_api_key = '9f3877175d9ff3ca95cb439ee8a96447'
tmdb_api_url = "https://api.themoviedb.org/3/movie/"

app = Flask(__name__)

CORS(app)

# Database (SQLite for local/dev). Change the URI for production DBs.
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movies.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    imdb_id = db.Column(db.String(32), unique=True, nullable=False)
    title = db.Column(db.String(256))
    poster_location = db.Column(db.String(512))
    release_date = db.Column(db.String(32))


def add_movie(imdb_id, title, poster_location=None, release_date=None):
    existing = Movie.query.filter_by(imdb_id=imdb_id).first()
    if existing:
        return existing
    m = Movie(imdb_id=imdb_id, title=title, poster_location=poster_location, release_date=release_date)
    db.session.add(m)
    db.session.commit()
    return m


def get_movie_by_imdb(imdb_id):
    return Movie.query.filter_by(imdb_id=imdb_id).first()


@app.route('/movies', methods=['POST'])

def create_movie():
    """Create a movie record. Requires JSON body with keys `id` and `title`.

    Accepts either `id` or `imdb_id` for the identifier. If poster_location or release_date are missing, fetch from TMDb.
    """
    data = request.get_json(silent=True) or {}
    imdb_id = data.get('id') or data.get('imdb_id')
    title = data.get('title')
    poster_location = data.get('poster_location') or data.get('posterPath') or data.get('poster_path')
    release_date = data.get('release_date') or data.get('releaseDate')

    if not imdb_id or not title:
        return jsonify({'error': 'Missing required fields: id and title'}), 400

    # If poster_location or release_date missing, fetch from TMDb
    if not poster_location or not release_date:
        tmdb_info = fetch_movie_by_imdb(imdb_id)
        if tmdb_info:
            if not poster_location:
                poster_location = tmdb_info.get('poster_path')
            if not release_date:
                release_date = tmdb_info.get('release_date')

    try:
        movie = add_movie(imdb_id, title, poster_location=poster_location, release_date=release_date)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'imdb_id': movie.imdb_id, 'title': movie.title, 'poster_location': movie.poster_location, 'release_date': movie.release_date}), 201



@app.route('/movies/all', methods=['GET'])
def list_movies():
    """Return all stored movies (imdb_id and title)."""
    movies = Movie.query.all()
    result = [{
        'imdb_id': m.imdb_id, 
        'title': m.title, 
        'poster_path': m.poster_location, 
        'release_date': m.release_date
        } for m in movies]
    return jsonify(result)


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


def fetch_movie_by_imdb(imdb_id):
    print("imdb # in fetch_movie_by_imdb", imdb_id, flush=True)
    """Return detailed TMDb info for a movie given its IMDb ID."""
    print(f"fetch_movie_by_imdb {imdb_id}", flush=True)
    # reuse logic from poster helper to get TMDb numeric id
    find_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    resp = requests.get(find_url, params={'api_key': tmdb_api_key, 'external_source': 'imdb_id'})
    print("find status", resp.status_code, flush=True)
    if resp.status_code != 200:
        return None
    data = resp.json()
    movies = data.get('movie_results') or []
    if not movies:
        return None
    tmdb_id = movies[0]['id']
    detail_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    resp2 = requests.get(detail_url, params={'api_key': tmdb_api_key})
    print("detail status", resp2.status_code, flush=True)
    if resp2.status_code == 200:
        return resp2.json()
    return None


@app.route('/movies/<imdb_id>', methods=['GET'])
def get_movie_by_id(imdb_id):
    """Lookup a movie via IMDb ID and return TMDb data."""
    info = fetch_movie_by_imdb(imdb_id)
    if info is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(info)


def ensure_schema():
    """Ensure new columns exist in the SQLite movie table."""
    insp = db.inspect(db.engine)
    if 'movie' in insp.get_table_names():
        cols = [row[1] for row in db.session.execute("PRAGMA table_info(movie)")]
        if 'poster_location' not in cols:
            db.session.execute('ALTER TABLE movie ADD COLUMN poster_location TEXT')
        if 'release_date' not in cols:
            db.session.execute('ALTER TABLE movie ADD COLUMN release_date TEXT')
        db.session.commit()


if __name__ == '__main__':
    # Ensure tables exist before starting the server.
    with app.app_context():
        db.create_all()

    # Run on all interfaces so the server is reachable remotely when hosted.
    app.run(debug=True)   # Running in debug mode reloads the server automatically on code changes
    # app.run(host='0.0.0.0', port=5000)