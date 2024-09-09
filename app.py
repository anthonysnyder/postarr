import os
import requests
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from difflib import get_close_matches
from PIL import Image  # Import Pillow to work with images
from datetime import datetime

app = Flask(__name__)

# Fetch TMDb API key from environment variables (use with Docker)
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Base URLs for TMDb API and images
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/original"

# Define the base folders for your movie directories
base_folders = [
    "/movies",
    "/kids-movies",
    "/movies2",
    "/kids-movies2"
]

# Function to normalize the movie title for consistent search queries
def normalize_title(title):
    return title.lower().replace("'", "").replace("-", "").replace(":", "").replace("&", "and").strip()

# Helper function to remove leading "The " for sorting purposes
def strip_leading_the(title):
    if title.lower().startswith("the "):
        return title[4:]  # Remove "The " (4 characters)
    return title

# Function to retrieve movie directories and their associated posters (thumbnails) for the index page
def get_poster_thumbnails():
    movies = []
    
    # Iterate over all base folders
    for base_folder in base_folders:
        for movie_dir in sorted(os.listdir(base_folder)):
            # Ignore @eadir directories
            if movie_dir == "@eadir":
                continue
            
            original_movie_dir = movie_dir  # Store the original directory name
            movie_path = os.path.join(base_folder, original_movie_dir)  # Use original name for paths
            
            # Check if the path is a directory (i.e., a movie directory)
            if os.path.isdir(movie_path):
                poster = None
                poster_dimensions = None  # Initialize poster dimensions
                poster_last_modified = None  # Initialize last modified date
                
                # Look for an existing poster in the directory
                for ext in ['jpg', 'jpeg', 'png']:
                    poster_path = os.path.join(movie_path, f"poster.{ext}")
                    if os.path.exists(poster_path):
                        # Generate the poster URL using the /poster/ route
                        poster = f"/poster/{urllib.parse.quote(original_movie_dir)}/poster.{ext}"
                        
                        # Extract poster dimensions using Pillow
                        try:
                            with Image.open(poster_path) as img:
                                width, height = img.size
                                poster_dimensions = f"{width}x{height}"
                        except Exception as e:
                            poster_dimensions = "Unknown"

                        # Get the last modified time of the poster and format only the date
                        timestamp = os.path.getmtime(poster_path)
                        poster_last_modified = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')  # Only date
                        
                        break

                # List all files in the movie directory (e.g., movie files)
                movie_files = os.listdir(movie_path)
                
                # Append movie details to the list, including poster dimensions and last modified date
                movies.append({
                    'title': original_movie_dir,
                    'poster': poster,
                    'poster_dimensions': poster_dimensions,  # Add poster dimensions
                    'poster_last_modified': poster_last_modified,  # Add last modified date (only date)
                    'movie_files': movie_files
                })
    

    # Sort the movies globally by title, ignoring "The" when sorting
    movies_sorted = sorted(movies, key=lambda x: strip_leading_the(x['title'].lower()))


    # Return the sorted list of movies and the total count
    return movies_sorted, len(movies_sorted)

# Route for the index page
@app.route('/')
def index():
    # Fetch the list of movies and their posters
    movies, total_movies = get_poster_thumbnails()  # Now returns both movies and the count
    
        # Render the index page with the movie data and total count
    return render_template('index.html', movies=movies, total_movies=total_movies)

# Route to refresh index.html
@app.route('/refresh')
def refresh():
    get_poster_thumbnails()  # Re-scan the directories
    return redirect(url_for('index'))

# Route for searching movies using TMDb API
@app.route('/search', methods=['GET'])
def search_movie():
    # Get the query string from the URL parameters
    query = request.args.get('query', '')
    
    # Normalize the search query (this will act as normalized_movie_dir)
    normalized_movie_dir = normalize_title(query)
    
    # Make a request to the TMDb API to search for movies
    response = requests.get(f"{BASE_URL}/search/movie", params={"api_key": TMDB_API_KEY, "query": normalized_movie_dir})
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
    
    # Sort posters by resolution (width * height)
    def poster_resolution(poster):
        # Extract width and height from the poster size (e.g., '1000x1500')
        dimensions = poster['width'], poster['height']
        return dimensions[0] * dimensions[1]  # Calculate the area of the poster
    
    posters_sorted = sorted(posters, key=poster_resolution, reverse=True)  # Sort by area in descending order

    # Format the poster URLs for display
    posters = [{'url': f"{POSTER_BASE_URL}{poster['file_path']}", 'size': f"{poster['width']}x{poster['height']}", 'language': poster['iso_639_1']} for poster in posters_sorted]

    # Render the poster selection page with the sorted posters
    return render_template('poster_selection.html', posters=posters, movie_title=movie_title)

import os

# Route for handling poster selection and downloading
@app.route('/select_poster', methods=['POST'])
def select_poster():
    # Get the selected poster path and movie title from the form submission
    poster_path = request.form['poster_path']
    movie_title = request.form['movie_title']

    # Initialize save_dir as None
    save_dir = None
    possible_dirs = []

    # Search for the correct directory based on the exact movie title
    for base_folder in base_folders:
        directories = os.listdir(base_folder)
        possible_dirs.extend(directories)
        for directory in directories:
            if directory == movie_title:
                save_dir = os.path.join(base_folder, directory)
                break
        if save_dir:
            break

    # If no exact match is found, present a dialog with similar directories
    if not save_dir:
        # Find similar directory names
        similar_dirs = get_close_matches(movie_title, possible_dirs, n=5, cutoff=0.5)
        return render_template('select_directory.html', similar_dirs=similar_dirs, movie_title=movie_title, poster_path=poster_path)

    # Define the new poster's save path with the .jpg extension
    save_path = os.path.join(save_dir, 'poster.jpg')

  # Remove any existing poster files with .jpg, .jpeg, or .png extensions
    for ext in ['jpg', 'jpeg', 'png']:
      for file in os.listdir(save_dir):
        if file.lower() == f'poster.{ext}':  # Make comparison case-insensitive
            os.remove(os.path.join(save_dir, file))  # Delete the existing poster file
 

    # Download and save the new poster (which will overwrite or replace the old one)
    poster_data = requests.get(poster_path).content
    with open(save_path, 'wb') as file:
        file.write(poster_data)

    # Send notification to Slack (if applicable)
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_webhook_url:
        message = {
            "text": f"Poster for '{movie_title}' has been downloaded and saved!",
            "attachments": [
                {
                    "text": f"Saved To\n{save_path}",
                    "image_url": poster_path
                }
            ]
        }
        requests.post(slack_webhook_url, json=message)

    # Redirect after saving
    return redirect(url_for('index') + f"#{anchor}")

# Route for confirming the directory and saving the poster
@app.route('/confirm_directory', methods=['POST'])
def confirm_directory():
    # Get the selected directory and other details from the form submission
    selected_directory = request.form['selected_directory']
    movie_title = request.form['movie_title']
    poster_path = request.form['poster_path']
    
    # Construct the save directory path
    for base_folder in base_folders:
        if selected_directory in os.listdir(base_folder):
            save_dir = os.path.join(base_folder, selected_directory)
            break

    # Define the full path for saving the poster
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

    return redirect(url_for('index', without_posters='true'))

# Route for serving posters
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