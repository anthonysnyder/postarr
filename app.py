import os
import requests
import re
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from difflib import get_close_matches, SequenceMatcher  # For string similarity
from PIL import Image  # For image processing
from datetime import datetime  # For handling dates and times

# Initialize the Flask application
app = Flask(__name__)

# Custom Jinja2 filter to remove years from movie titles (e.g., 1995, 2020)
@app.template_filter('remove_year')
def remove_year(value):
    # Remove years in the format 19xx, 20xx, 21xx, 22xx, or 23xx
    return re.sub(r'\b(19|20|21|22|23)\d{2}\b', '', value).strip()

# Fetch TMDb API key from environment variables
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Base URLs for TMDb API and images
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/original"

# Define folder paths for movies and TV shows
MOVIE_FOLDERS = ["/movies", "/kids-movies", "/movies2", "/kids-movies2"]
TV_FOLDERS = ["/tv", "/kids-tv", "/tv2", "/kids-tv2"]

# Function to normalize movie titles for consistent search and comparison
def normalize_title(title):
    # Remove all non-alphanumeric characters and convert to lowercase
    return re.sub(r'[^a-z0-9]+', '', title.lower())

# Helper function to remove leading "The " from titles for sorting purposes
def strip_leading_the(title):
    if title.lower().startswith("the "):
        return title[4:]  # Remove "The " (4 characters)
    return title

# Function to generate a clean, anchor-safe ID from the movie title
def generate_clean_id(title):
    # Replace all non-alphanumeric characters with dashes and strip leading/trailing dashes
    clean_id = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return clean_id

import os
import urllib.parse

def get_movie_thumbnails():
    movies = []
    for folder in MOVIE_FOLDERS:
        for movie_dir in os.listdir(folder):
            movie_path = os.path.join(folder, movie_dir)
            if os.path.isdir(movie_path):
                has_poster = False
                poster_thumb = None
                for ext in ['jpg', 'jpeg', 'png']:
                    thumb_path = os.path.join(movie_path, f"poster-thumb.{ext}")
                    if os.path.exists(thumb_path):
                        poster_thumb = f"/poster/{urllib.parse.quote(movie_dir)}/poster-thumb.{ext}?content_type=movie"
                        has_poster = True
                        break
                movies.append({
                    'title': movie_dir,
                    'poster_thumb': poster_thumb,
                    'has_poster': has_poster
                })
    # Sort movies alphabetically
    movies = sorted(movies, key=lambda x: x['title'].lower())
    return movies

def get_tv_show_thumbnails():
    tv_shows = []
    for folder in TV_FOLDERS:
        for show_dir in os.listdir(folder):
            show_path = os.path.join(folder, show_dir)
            if os.path.isdir(show_path):
                has_poster = False
                poster_thumb = None
                for ext in ['jpg', 'jpeg', 'png']:
                    thumb_path = os.path.join(show_path, f"poster-thumb.{ext}")
                    if os.path.exists(thumb_path):
                        poster_thumb = f"/poster/{urllib.parse.quote(show_dir)}/poster-thumb.{ext}?content_type=tv"
                        has_poster = True
                        break
                tv_shows.append({
                    'title': show_dir,
                    'poster_thumb': poster_thumb,
                    'has_poster': has_poster
                })
    # Sort TV shows alphabetically
    tv_shows = sorted(tv_shows, key=lambda x: x['title'].lower())
    return tv_shows

# Route for the index page
@app.route('/')
def index():
    content_type = request.args.get('content_type', 'movie')
    if content_type == 'movie':
        media = get_movie_thumbnails()
    else:
        media = get_tv_show_thumbnails()
    
    total_count = len(media)
    return render_template('index.html', media=media, total_count=total_count, content_type=content_type)

# Route to refresh index.html (if needed)
@app.route('/refresh')
def refresh():
    get_poster_thumbnails()  # Re-scan the directories
    return redirect(url_for('index'))

# Route for searching movies using TMDb API
@app.route('/search', methods=['GET'])
def search_movie():
    # Get the query string from the URL parameters
    query = request.args.get('query', '')

    # Make a request to the TMDb API to search for movies matching the query
    response = requests.get(f"{BASE_URL}/search/movie", params={"api_key": TMDB_API_KEY, "query": query})
    results = response.json().get('results', [])

    # Normalize TMDb titles using generate_clean_id for consistency
    for result in results:
        result['clean_id'] = generate_clean_id(result['title'])

    # Render the search_results.html template with the movies found
    return render_template('search_results.html', query=query, results=results)

# Route for selecting a movie and displaying available posters
@app.route('/select_movie/<int:movie_id>', methods=['GET'])
def select_movie(movie_id):
    # Request details of the selected movie from TMDb API
    movie_details = requests.get(f"{BASE_URL}/movie/{movie_id}", params={"api_key": TMDB_API_KEY}).json()

    # Extract the movie title and generate clean_id
    movie_title = movie_details.get('title', '')
    clean_id = generate_clean_id(movie_title)

    # Request available posters for the selected movie
    posters = requests.get(f"{BASE_URL}/movie/{movie_id}/images", params={"api_key": TMDB_API_KEY}).json().get('posters', [])

    # Filter posters to only include English language posters
    posters = [poster for poster in posters if poster['iso_639_1'] == 'en']

    # Function to calculate the resolution (area) of a poster
    def poster_resolution(poster):
        dimensions = poster['width'], poster['height']
        return dimensions[0] * dimensions[1]  # Width * Height

    # Sort posters by resolution in descending order (highest resolution first)
    posters_sorted = sorted(posters, key=poster_resolution, reverse=True)

    # Format the poster URLs and details for display
    posters = [{
        'url': f"{POSTER_BASE_URL}{poster['file_path']}",
        'size': f"{poster['width']}x{poster['height']}",
        'language': poster['iso_639_1']
    } for poster in posters_sorted]

    # Render the poster_selection.html template with the sorted posters and clean_id
    return render_template('poster_selection.html', posters=posters, movie_title=movie_title, clean_id=clean_id)

# Function to handle poster selection and download, including thumbnail creation
def save_poster_and_thumbnail(poster_url, movie_title, save_dir):
    full_poster_path = os.path.join(save_dir, 'poster.jpg')
    thumb_poster_path = os.path.join(save_dir, 'poster-thumb.jpg')

    try:
        # Delete existing poster files in the directory (if any)
        for ext in ['jpg', 'jpeg', 'png']:
            existing_poster = os.path.join(save_dir, f'poster.{ext}')
            existing_thumb = os.path.join(save_dir, f'poster-thumb.{ext}')
            if os.path.exists(existing_poster):
                os.remove(existing_poster)
            if os.path.exists(existing_thumb):
                os.remove(existing_thumb)

        # Download the full-resolution poster
        response = requests.get(poster_url)
        if response.status_code == 200:
            # Save the downloaded poster image
            with open(full_poster_path, 'wb') as file:
                file.write(response.content)

            # Create the thumbnail using Pillow
            with Image.open(full_poster_path) as img:
                # Calculate aspect ratio
                aspect_ratio = img.width / img.height
                target_ratio = 300 / 450  # Desired thumbnail ratio

                if aspect_ratio > target_ratio:
                    # Image is wider than desired ratio, crop the sides
                    new_width = int(img.height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # Image is taller than desired ratio, crop the top and bottom
                    new_height = int(img.width / target_ratio)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, img.width, top + new_height))

                # Resize the image to 300x450 pixels
                img = img.resize((300, 450), Image.LANCZOS)

                # Save the thumbnail image
                img.save(thumb_poster_path, "JPEG", quality=90)

            print(f"Poster and thumbnail saved successfully for '{movie_title}'")
            return full_poster_path  # Return the local path where the poster was saved
        else:
            print(f"Failed to download poster for '{movie_title}'. Status code: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error saving poster and generating thumbnail for '{movie_title}': {e}")
        return None

# Route for handling poster selection and downloading
@app.route('/select_poster', methods=['POST'])
def select_poster():
    # Get the selected poster URL and movie title from the form submission
    poster_url = request.form['poster_path']
    movie_title = request.form['movie_title']

    # Initialize variables
    save_dir = None
    possible_dirs = []

    # Normalize the movie title for comparison
    normalized_movie_title = normalize_title(movie_title)

    # Variables to keep track of the best match
    best_similarity = 0
    best_match_dir = None

    # Search for the correct directory based on the exact movie title
    for base_folder in base_folders:
        directories = os.listdir(base_folder)
        possible_dirs.extend(directories)  # Collect all possible directories
        for directory in directories:
            if directory == movie_title:
                # Exact match found
                save_dir = os.path.join(base_folder, directory)
                break
            else:
                # Normalize the directory name for comparison
                normalized_dir_name = normalize_title(directory)
                # Compute similarity between normalized titles
                similarity = SequenceMatcher(None, normalized_movie_title, normalized_dir_name).ratio()
                # Keep track of the best match
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_dir = os.path.join(base_folder, directory)
        if save_dir:
            # Exit the loop if exact match is found
            break

    # If an exact match was found, proceed to save the poster
    if save_dir:
        # Save the poster and get the local path
        local_poster_path = save_poster_and_thumbnail(poster_url, movie_title, save_dir)
        if local_poster_path:
            # Send Slack notification with the local path
            message = f"Poster for '{movie_title}' has been downloaded!"
            send_slack_notification(message, local_poster_path, poster_url)
        else:
            print(f"Failed to save poster for '{movie_title}'")
        # Create anchor for navigation
        clean_id = generate_clean_id(movie_title)
        # Redirect back to the index page with an anchor to the selected movie
        return redirect(url_for('index') + f"#{clean_id}")
    else:
        # No exact match found, check if best similarity is above the threshold
        similarity_threshold = 0.8  # Threshold between 0 and 1 (e.g., 80% similarity)
        if best_similarity >= similarity_threshold:
            # Automatically select the directory with the highest similarity
            save_dir = best_match_dir
            # Log the automatic selection
            print(f"Automatically selected directory '{save_dir}' for movie '{movie_title}' with similarity {best_similarity:.2f}")
            # Save the poster and get the local path
            local_poster_path = save_poster_and_thumbnail(poster_url, movie_title, save_dir)
            if local_poster_path:
                # Send Slack notification with the local path
                message = f"Poster for '{movie_title}' has been downloaded!"
                send_slack_notification(message, local_poster_path, poster_url)
            else:
                print(f"Failed to save poster for '{movie_title}'")
            # Create anchor for navigation
            clean_id = generate_clean_id(movie_title)
            # Redirect back to the index page with an anchor to the selected movie
            return redirect(url_for('index') + f"#{clean_id}")
        else:
            # Similarity below threshold, prompt user to select directory manually
            # Log the need for manual selection
            print(f"No suitable directory found for '{movie_title}'. Best match similarity: {best_similarity:.2f}")
            # Find similar directory names to present to the user
            similar_dirs = get_close_matches(movie_title, possible_dirs, n=5, cutoff=0.5)
            # Render the select_directory.html template for user to choose
            return render_template('select_directory.html', similar_dirs=similar_dirs, movie_title=movie_title, poster_path=poster_url)

# Route for serving posters from the file system
@app.route('/poster/<path:filename>')
def serve_poster(filename):
    # Check if a "refresh" flag is present in the URL query parameters
    refresh = request.args.get('refresh', 'false')
    for base_folder in base_folders:
        full_path = os.path.join(base_folder, filename)  # Construct the full path to the poster file
        # Ignore files within @eaDir (special directory used by Synology NAS)
        if '@eaDir' in full_path:
            continue
        if os.path.exists(full_path):
            # Serve the file from the appropriate directory
            response = send_from_directory(base_folder, filename)
            if refresh == 'true':
                # If refresh is requested, set cache headers to force re-download
                response.cache_control.no_cache = True
                response.cache_control.must_revalidate = True
                response.cache_control.max_age = 0
            else:
                # If no refresh is requested, set cache headers for 1 year
                response.cache_control.max_age = 31536000  # 1 year in seconds
            return response  # Return the response with the file
    # If the file doesn't exist, return a 404 error
    return "File not found", 404

# Route for confirming the directory and saving the poster (used when manual selection is required)
@app.route('/confirm_directory', methods=['POST'])
def confirm_directory():
    # Get the selected directory and other details from the form submission
    selected_directory = request.form['selected_directory']
    movie_title = request.form['movie_title']
    poster_url = request.form['poster_path']

    # Construct the save directory path based on the selected directory
    save_dir = None
    for base_folder in base_folders:
        if selected_directory in os.listdir(base_folder):
            save_dir = os.path.join(base_folder, selected_directory)
            break

    if not save_dir:
        # Directory not found, log an error and return 404
        print(f"Selected directory '{selected_directory}' not found in base folders.")
        return "Directory not found", 404

    # Save the poster and get the local path
    local_poster_path = save_poster_and_thumbnail(poster_url, movie_title, save_dir)
    if local_poster_path:
        # Send Slack notification with the local path
        message = f"Poster for '{movie_title}' has been downloaded!"
        send_slack_notification(message, local_poster_path, poster_url)
    else:
        print(f"Failed to save poster for '{movie_title}'")

    # Generate clean_id for navigation
    anchor = generate_clean_id(movie_title)
    # Redirect back to the index page with an anchor to the selected movie
    return redirect(url_for('index') + f"#{anchor}")

# Function to send Slack notifications (if a webhook URL is configured)
def send_slack_notification(message, local_poster_path, poster_url):
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_webhook_url:
        payload = {
            "text": message,
            "attachments": [
                {
                    "text": f"Poster saved to: {local_poster_path}",
                    "image_url": poster_url  # Use the original TMDb image URL to display the poster in Slack
                }
            ]
        }
        try:
            response = requests.post(slack_webhook_url, json=payload)
            if response.status_code == 200:
                print(f"Slack notification sent successfully for '{local_poster_path}'")
            else:
                print(f"Failed to send Slack notification. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error sending Slack notification: {e}")
    else:
        print("Slack webhook URL not set.")

# Route for refreshing index.html (alternative if needed)
@app.route('/refresh')
def refresh_page():
    return redirect(url_for('index', refresh='true'))

# Entry point for running the Flask application
if __name__ == '__main__':
    # Run the app, listening on all network interfaces at port 5000
    app.run(host='0.0.0.0', port=5000)
