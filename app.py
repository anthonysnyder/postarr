import os
import requests
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)

# Fetch TMDb API key from environment variables (use with Docker)
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Base URLs for TMDb API and images
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

# Define the base folders for your movie directories
base_folders = [
    "/movies",
    "/kids-movies",
    "/movies2",
    "/kids-movies2"
]

# Function to retrieve movie directories and their associated posters (thumbnails) for the index page
def get_poster_thumbnails():
    movies = []
    
    # Iterate over all base folders
    for base_folder in base_folders:
        # Get sorted list of directories (movies) within each base folder
        for movie_dir in sorted(os.listdir(base_folder)):
            movie_path = os.path.join(base_folder, movie_dir)
            
            # Check if the path is a directory (i.e., a movie directory)
            if os.path.isdir(movie_path):
                poster = None
                
                # Look for an existing poster in the directory
                for ext in ['jpg', 'jpeg', 'png']:
                    poster_path = os.path.join(movie_path, f"poster.{ext}")
                    if os.path.exists(poster_path):
                        poster = f"/poster/{urllib.parse.quote(movie_dir)}/poster.{ext}"
                        break

                # List all files in the movie directory (e.g., movie files)
                movie_files = os.listdir(movie_path)
                
                # Append movie details to the list
                movies.append({
                    'title': movie_dir,
                    'poster': poster,
                    'movie_files': movie_files
                })
    
    # Return the list of movies and their associated posters
    return movies

# Route for the index page
@app.route('/')
def index():
    # Get the list of movies with thumbnails
    movies = get_poster_thumbnails()
    
    # Render the index page with the movie data
    return render_template('index.html', movies=movies)

# Route for searching movies using TMDb API
@app.route('/search', methods=['GET'])
def search_movie():
    # Get the query string from the URL parameters
    query = request.args.get('query', '')
    
    # Clean the query by removing any year and parentheses
    cleaned_query = query.replace("(", "").replace(")", "").strip()
    
    # Make a request to the TMDb API to search for movies
    response = requests.get(f"{BASE_URL}/search/movie", params={"api_key": TMDB_API_KEY, "query": cleaned_query})
    results = response.json().get('results', [])
    
    # Render the search results page with the movies found
    return render_template('search_results.html', query=query, results=results)

# Route for selecting a movie and displaying available posters
@app.route('/select_movie/<int:movie_id>', methods=['GET'])
def select_movie(movie_id):
    # Request details of the selected movie from TMDb API
    movie_details = requests.get(f"{BASE_URL}/movie/{movie_id}", params={"api_key": TMDB_API_KEY}).json()
    
    # Extract the movie title from the details
    movie_title = movie_details.get('title', '')
    
    # Request available posters for the selected movie
    posters = requests.get(f"{BASE_URL}/movie/{movie_id}/images", params={"api_key": TMDB_API_KEY}).json().get('posters', [])
    
    # Filter posters to only include English ones
    posters = [poster for poster in posters if poster['iso_639_1'] == 'en']
    
    # Format the poster URLs for display
    posters = [{'url': f"{POSTER_BASE_URL}{poster['file_path']}", 'size': f"{poster['width']}x{poster['height']}"} for poster in posters]
    
    # Render the poster selection page with the available posters
    return render_template('poster_selection.html', posters=posters, movie_title=movie_title)

# Route for handling poster selection and downloading
@app.route('/select_poster', methods=['POST'])
def select_poster():
    # Get the selected poster path and movie title from the form submission
    poster_path = request.form['poster_path']
    movie_title = request.form['movie_title']
    
    # Determine the correct save directory based on the movie title
    save_dir = None
    for base_folder in base_folders:
        potential_save_dir = os.path.join(base_folder, movie_title)
        if os.path.exists(potential_save_dir):
            save_dir = potential_save_dir
            break

    # If no existing directory is found, create one in the first base folder
    if not save_dir:
        save_dir = os.path.join(base_folders[0], movie_title)
        os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, 'poster.jpg')

    # Download and save the poster
    poster_data = requests.get(poster_path).content
    with open(save_path, 'wb') as file:
        file.write(poster_data)

    # Send notification to Slack
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_webhook_url:
        message = {
            "text": f"Poster for '{movie_title}' has been downloaded!",
            "attachments": [
                {
                    "text": f"Saved To\n{save_path}",
                    "image_url": poster_path
                }
            ]
        }
        requests.post(slack_webhook_url, json=message)

    return redirect(url_for('index'))

# Route to serve posters from the movie directories
@app.route('/poster/<path:filename>')
def serve_poster(filename):
    # Determine which base folder contains the requested file
    for base_folder in base_folders:
        full_path = os.path.join(base_folder, filename)
        if os.path.exists(full_path):
            return send_from_directory(base_folder, filename)
    return "File not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
