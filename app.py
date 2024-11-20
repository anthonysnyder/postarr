import os
import requests
import re
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from difflib import get_close_matches, SequenceMatcher  # For string similarity
from PIL import Image  # For image processing
from datetime import datetime  # For handling dates and times
from urllib.parse import unquote


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

# Define base folders for movies and TV shows
movie_folders = ["/movies", "/kids-movies", "/movies2", "/kids-movies2"]
tv_folders = ["/tv", "/kids-tv", "/tv2", "/kids-tv2"]  # Ensure these folders are accessible

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

# Function to retrieve movie directories and their associated posters for the index page
def get_poster_thumbnails(base_folders=None):
    if base_folders is None:
        base_folders = movie_folders  # Default to movie folders if none provided
    media_list = []

    # Iterate over each specified base folder (movies or TV shows)
    for base_folder in base_folders:
        for media_dir in sorted(os.listdir(base_folder)):
            if media_dir == "@eadir":  # Skip Synology NAS system folders
                continue

            media_path = os.path.join(base_folder, media_dir)

            if os.path.isdir(media_path):
                poster = None
                poster_thumb = None
                poster_dimensions = None
                poster_last_modified = None

                # Search for poster files in the directory
                for ext in ['jpg', 'jpeg', 'png']:
                    thumb_path = os.path.join(media_path, f"poster-thumb.{ext}")
                    poster_path = os.path.join(media_path, f"poster.{ext}")

                    if os.path.exists(thumb_path):
                        poster_thumb = f"/poster/{urllib.parse.quote(media_dir)}/poster-thumb.{ext}"

                    if os.path.exists(poster_path):
                        poster = f"/poster/{urllib.parse.quote(media_dir)}/poster.{ext}"

                        try:
                            with Image.open(poster_path) as img:
                                poster_dimensions = f"{img.width}x{img.height}"
                        except Exception:
                            poster_dimensions = "Unknown"

                        timestamp = os.path.getmtime(poster_path)
                        poster_last_modified = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                        break

                clean_id = generate_clean_id(media_dir)
                media_list.append({
                    'title': media_dir,
                    'poster': poster,
                    'poster_thumb': poster_thumb,
                    'poster_dimensions': poster_dimensions,
                    'poster_last_modified': poster_last_modified,
                    'clean_id': clean_id,
                    'has_poster': bool(poster_thumb)
                })

    media_list = sorted(media_list, key=lambda x: strip_leading_the(x['title'].lower()))
    return media_list, len(media_list)

# Route for the index page
@app.route('/')
def index():
    movies, total_movies = get_poster_thumbnails(movie_folders)
    
    # Render the index.html template with the movie data and total count
    return render_template('index.html', movies=movies, total_movies=total_movies)

# Route for TV shows page
@app.route('/tv')
def tv_shows():
    tv_shows, total_tv_shows = get_poster_thumbnails(tv_folders)

    # Log the TV shows data for debugging
    app.logger.info(f"Fetched TV shows: {tv_shows}")

    return render_template('tv.html', tv_shows=tv_shows, total_tv_shows=total_tv_shows)

# Route to refresh index.html (if needed)
@app.route('/refresh')
def refresh():
    get_poster_thumbnails()  # Re-scan the directories
    return redirect(url_for('index'))

# Route for searching movies using TMDb API
@app.route('/search_movie', methods=['GET'])
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

# Route for searching TV shows using TMDb API
@app.route('/search_tv', methods=['GET'])
def search_tv():
    query = unquote(request.args.get('query', ''))

    # Log the received query
    app.logger.info(f"Search TV query received: {query}")

    response = requests.get(f"{BASE_URL}/search/tv", params={"api_key": TMDB_API_KEY, "query": query, "include_adult": False, "language": "en-US", "page": 1})
    results = response.json().get('results', [])

    # Log the fetched results
    app.logger.info(f"TMDb API returned {len(results)} results for query: {query}")

    for result in results:
        result['clean_id'] = generate_clean_id(result['name'])
        app.logger.info(f"Result processed: {result['name']} -> Clean ID: {result['clean_id']}")

    return render_template('search_results.html', query=query, results=results, content_type="tv")

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
        return poster['width'] * poster['height']  # Width * Height

    # Sort posters by resolution in descending order (highest resolution first)
    posters_sorted = sorted(posters, key=poster_resolution, reverse=True)

    # Format the poster URLs and details for display
    formatted_posters = [{
        'url': f"{POSTER_BASE_URL}{poster['file_path']}",
        'size': f"{poster['width']}x{poster['height']}",
        'language': poster['iso_639_1']
    } for poster in posters_sorted]

    # Render the poster_selection.html template with the sorted posters, movie title, and type
    return render_template('poster_selection.html', media_title=movie_title, content_type='movie', posters=formatted_posters)


# Route for selecting a TV show and displaying available posters
@app.route('/select_tv/<int:tv_id>', methods=['GET'])
def select_tv(tv_id):
    # Request details of the selected TV show from TMDb API
    tv_details = requests.get(f"{BASE_URL}/tv/{tv_id}", params={"api_key": TMDB_API_KEY}).json()

    # Extract the TV show title and generate clean_id
    tv_title = tv_details.get('name', '')
    clean_id = generate_clean_id(tv_title)

    # Request available posters for the selected TV show
    posters = requests.get(f"{BASE_URL}/tv/{tv_id}/images", params={"api_key": TMDB_API_KEY}).json().get('posters', [])

    # Filter posters to only include English language posters
    posters = [poster for poster in posters if poster['iso_639_1'] == 'en']

    # Sort posters by resolution in descending order (highest resolution first)
    posters_sorted = sorted(posters, key=lambda p: p['width'] * p['height'], reverse=True)

    # Format the poster URLs and details for display
    formatted_posters = [{
        'url': f"{POSTER_BASE_URL}{poster['file_path']}",
        'size': f"{poster['width']}x{poster['height']}",
        'language': poster['iso_639_1']
    } for poster in posters_sorted]

    # Render the poster_selection.html template with the sorted posters, tv title, and type
    return render_template('poster_selection.html', posters=formatted_posters, media_title=tv_title, clean_id=clean_id, content_type="tv")
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
    # Log the received form data for debugging
    app.logger.info("Received form data: %s", request.form)

    # Validate required form data
    if 'poster_path' not in request.form or 'media_title' not in request.form or 'media_type' not in request.form:
        app.logger.error("Missing form data: %s", request.form)
        return "Bad Request: Missing form data", 400

    try:
        # Extract form data
        poster_url = request.form['poster_path']
        media_title = request.form['media_title']
        media_type = request.form['media_type']  # Should be either 'movie' or 'tv'

        # Add the logger here
        app.logger.info(f"Poster Path: {poster_url}, Media Title: {media_title}, Media Type: {media_type}")

        # Choose base folders based on media type
        base_folders = movie_folders if media_type == 'movie' else tv_folders

        # Initialize variables for directory search
        save_dir = None
        possible_dirs = []
        best_similarity = 0
        best_match_dir = None

        # Normalize media title for comparison
        normalized_media_title = normalize_title(media_title)

        # Search for an exact or closest matching directory
        for base_folder in base_folders:
            directories = os.listdir(base_folder)
            possible_dirs.extend(directories)

            for directory in directories:
                normalized_dir_name = normalize_title(directory)
                similarity = SequenceMatcher(None, normalized_media_title, normalized_dir_name).ratio()

                # Update if this is the best match
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_dir = os.path.join(base_folder, directory)

                if directory == media_title:
                    save_dir = os.path.join(base_folder, directory)
                    break

            if save_dir:
                break

        # If an exact match is found, proceed with downloading
        if save_dir:
            local_poster_path = save_poster_and_thumbnail(poster_url, media_title, save_dir)
            if local_poster_path:
                message = f"Poster for '{media_title}' has been downloaded!"
                send_slack_notification(message, local_poster_path, poster_url)
            return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # Use the best similarity above a threshold if no exact match
        similarity_threshold = 0.8
        if best_similarity >= similarity_threshold:
            save_dir = best_match_dir
            local_poster_path = save_poster_and_thumbnail(poster_url, media_title, save_dir)
            if local_poster_path:
                message = f"Poster for '{media_title}' has been downloaded!"
                send_slack_notification(message, local_poster_path, poster_url)
            return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # If no suitable directory, present options to the user
        similar_dirs = get_close_matches(media_title, possible_dirs, n=5, cutoff=0.5)
        return render_template('select_directory.html', similar_dirs=similar_dirs, media_title=media_title, poster_path=poster_url, media_type=media_type)

    except FileNotFoundError as fnf_error:
        app.logger.error("File not found: %s", fnf_error)
        return "Directory not found", 404
    except Exception as e:
        app.logger.exception("Unexpected error in select_poster route: %s", e)
        return "Internal Server Error", 500

# Route for serving posters from the file system
@app.route('/poster/<path:filename>')
def serve_poster(filename):
    # Combine movie and tv folders to search both sets of paths
    base_folders = movie_folders + tv_folders  # Check both movie and TV folders

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

    # Log an error message if the file is not found
    app.logger.error(f"File not found for {filename} in any base folder.")
    # If the file doesn't exist, return a 404 error
    return "File not found", 404

# Route for confirming the directory and saving the poster (used when manual selection is required)
@app.route('/confirm_directory', methods=['POST'])
def confirm_directory():
    # Log the form data for debugging
    selected_directory = request.form.get('selected_directory')
    movie_title = request.form.get('media_title')
    poster_url = request.form.get('poster_path')
    content_type = request.form.get('content_type', 'movie')  # Default to 'movie' if content_type isn't provided

    # Log all received form data
    app.logger.info(f"Received data: selected_directory={selected_directory}, movie_title={movie_title}, poster_url={poster_url}, content_type={content_type}")

    # Validate form data
    if not selected_directory or not movie_title or not poster_url:
        app.logger.error("Missing form data: selected_directory=%s, media_title=%s, poster_url=%s",
                         selected_directory, movie_title, poster_url)
        return "Bad Request: Missing form data", 400

    # Construct the save directory path based on the selected directory
    save_dir = None
    base_folders = movie_folders if content_type == 'movie' else tv_folders

    for base_folder in base_folders:
        if selected_directory in os.listdir(base_folder):
            save_dir = os.path.join(base_folder, selected_directory)
            break

    if not save_dir:
        # Directory not found, log an error and return 404
        app.logger.error(f"Selected directory '{selected_directory}' not found in base folders.")
        return "Directory not found", 404

    # Save the poster and get the local path
    local_poster_path = save_poster_and_thumbnail(poster_url, movie_title, save_dir)
    if local_poster_path:
        # Send Slack notification with the local path
        message = f"Poster for '{movie_title}' has been downloaded!"
        send_slack_notification(message, local_poster_path, poster_url)
        app.logger.info(f"Poster successfully saved to {local_poster_path}")
    else:
        app.logger.error(f"Failed to save poster for '{movie_title}'")
        return "Failed to save poster", 500

    # Generate clean_id for navigation
    anchor = generate_clean_id(movie_title)
    
    # Determine redirect URL based on content type
    redirect_url = url_for('index') if content_type == 'movie' else url_for('tv_shows')

    # Log the redirect URL for verification
    app.logger.info(f"Redirect URL: {redirect_url}#{anchor}")

    return redirect(f"{redirect_url}#{anchor}")

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
