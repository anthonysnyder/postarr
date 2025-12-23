import os
import requests
import re
import urllib.parse
import json
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from difflib import get_close_matches, SequenceMatcher  # For string similarity
from PIL import Image  # For image processing
from datetime import datetime  # For handling dates and times
from urllib.parse import unquote

# Initialize Flask application for managing movie and TV show posters
app = Flask(__name__)

# Custom Jinja2 filter to remove year information from movie titles for cleaner display
@app.template_filter('remove_year')
def remove_year(value):
    # Regex to remove years in the format 19xx, 20xx, 21xx, 22xx, or 23xx
    return re.sub(r'\b(19|20|21|22|23)\d{2}\b', '', value).strip()

# Fetch TMDb API key from environment variables for movie/TV show metadata
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Base URLs for TMDb API and poster images
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/original"

# Define base folders for organizing movies and TV shows
# Environment variables allow flexible folder configuration without code changes
movie_folders_env = os.getenv('MOVIE_FOLDERS', '/movies,/kids-movies,/anime')
tv_folders_env = os.getenv('TV_FOLDERS', '/tv,/kids-tv')

# Parse comma-separated folder lists and filter out non-existent paths
movie_folders = [folder.strip() for folder in movie_folders_env.split(',') if folder.strip() and os.path.exists(folder.strip())]
tv_folders = [folder.strip() for folder in tv_folders_env.split(',') if folder.strip() and os.path.exists(folder.strip())]

# Log the folders being used for verification
app.logger.info(f"Movie folders: {movie_folders}")
app.logger.info(f"TV folders: {tv_folders}")

# Path to the mapping file that stores TMDb ID -> Directory relationships
MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'tmdb_directory_mapping.json')

# Function to normalize movie/TV show titles for consistent searching and comparison
def normalize_title(title):
    # Remove all non-alphanumeric characters and convert to lowercase
    return re.sub(r'[^a-z0-9]+', '', title.lower())

# Helper function to remove leading "The " from titles for more accurate sorting
def strip_leading_the(title):
    if title.lower().startswith("the "):
        return title[4:]  # Remove "The " (4 characters)
    return title

# Function to generate a URL-friendly and anchor-safe ID from the media title
def generate_clean_id(title):
    # Replace all non-alphanumeric characters with dashes and strip leading/trailing dashes
    clean_id = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return clean_id

# Function to load the TMDb ID to directory mapping from disk
def load_directory_mapping():
    """Load the mapping file that remembers which TMDb IDs go to which directories"""
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            app.logger.error(f"Error loading mapping file: {e}")
            return {}
    return {}

# Function to save the TMDb ID to directory mapping to disk
def save_directory_mapping(mapping):
    """Save the mapping file to remember which TMDb IDs go to which directories"""
    try:
        with open(MAPPING_FILE, 'w') as f:
            json.dump(mapping, f, indent=2)
        app.logger.info(f"Saved directory mapping to {MAPPING_FILE}")
    except Exception as e:
        app.logger.error(f"Error saving mapping file: {e}")

# Function to get directory from mapping for a given TMDb ID and media type
def get_mapped_directory(tmdb_id, media_type):
    """Check if we already know which directory this TMDb ID belongs to"""
    mapping = load_directory_mapping()
    key = f"{media_type}_{tmdb_id}"
    mapped_dir = mapping.get(key)
    if mapped_dir and os.path.exists(mapped_dir):
        app.logger.info(f"Found existing mapping: {key} -> {mapped_dir}")
        return mapped_dir
    elif mapped_dir:
        app.logger.warning(f"Mapped directory no longer exists: {mapped_dir}, removing mapping")
        # Clean up invalid mapping
        del mapping[key]
        save_directory_mapping(mapping)
    return None

# Function to save a new TMDb ID to directory mapping
def save_mapped_directory(tmdb_id, media_type, directory_path):
    """Remember which directory this TMDb ID belongs to for next time"""
    mapping = load_directory_mapping()
    key = f"{media_type}_{tmdb_id}"
    mapping[key] = directory_path
    save_directory_mapping(mapping)
    app.logger.info(f"Saved new mapping: {key} -> {directory_path}")

# Function to retrieve media directories and their associated logo thumbnails
def get_logo_thumbnails(base_folders=None):
    # Default to movie folders if no folders specified
    if base_folders is None:
        base_folders = movie_folders
    media_list = []

    # Iterate through specified base folders to find media with logos
    for base_folder in base_folders:
        for media_dir in sorted(os.listdir(base_folder)):
            if media_dir.lower() in ["@eadir", "#recycle"]:  # Skip Synology NAS system folders (case-insensitive)
                continue

            media_path = os.path.join(base_folder, media_dir)

            if os.path.isdir(media_path):
                logo = None
                logo_thumb = None
                logo_dimensions = None
                logo_last_modified = None

                # Search for logo files in PNG format (logos typically have transparency)
                for ext in ['png', 'jpg', 'jpeg']:
                    thumb_path = os.path.join(media_path, f"logo-thumb.{ext}")
                    logo_path = os.path.join(media_path, f"logo.{ext}")

                    # Store thumbnail and full logo paths for web serving
                    if os.path.exists(thumb_path):
                        logo_thumb = f"/logo/{urllib.parse.quote(media_dir)}/logo-thumb.{ext}"

                    if os.path.exists(logo_path):
                        logo = f"/logo/{urllib.parse.quote(media_dir)}/logo.{ext}"

                        # Get logo image dimensions
                        try:
                            with Image.open(logo_path) as img:
                                logo_dimensions = f"{img.width}x{img.height}"
                        except Exception:
                            logo_dimensions = "Unknown"

                        # Get last modified timestamp of the logo
                        timestamp = os.path.getmtime(logo_path)
                        logo_last_modified = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                        break

                # Generate a clean ID for HTML anchor and URL purposes
                clean_id = generate_clean_id(media_dir)
                media_list.append({
                    'title': media_dir,
                    'logo': logo,
                    'logo_thumb': logo_thumb,
                    'logo_dimensions': logo_dimensions,
                    'logo_last_modified': logo_last_modified,
                    'clean_id': clean_id,
                    'has_logo': bool(logo_thumb)
                })

    # Sort media list, ignoring leading "The" for more natural sorting
    media_list = sorted(media_list, key=lambda x: strip_leading_the(x['title'].lower()))
    return media_list, len(media_list)

# Route for the main index page showing movie logos
@app.route('/')
def index():
    movies, total_movies = get_logo_thumbnails(movie_folders)

    # Render the index page with movie thumbnails and total count
    return render_template('index.html', movies=movies, total_movies=total_movies)

# Route for TV shows page
@app.route('/tv')
def tv_shows():
    tv_shows, total_tv_shows = get_logo_thumbnails(tv_folders)

    # Log TV shows data for debugging
    app.logger.info(f"Fetched TV shows: {tv_shows}")

    return render_template('tv.html', tv_shows=tv_shows, total_tv_shows=total_tv_shows)

# Route to trigger a manual refresh of media directories
@app.route('/refresh')
def refresh():
    get_logo_thumbnails()  # Re-scan the directories
    return redirect(url_for('index'))

# Route for searching movies using TMDb API
@app.route('/search_movie', methods=['GET'])
def search_movie():
    # Get search query and directory name from URL parameters
    query = request.args.get('query', '')
    directory = request.args.get('directory', '')  # Get the directory name from the original movie card click

    # Search movies on TMDb using the API
    response = requests.get(f"{BASE_URL}/search/movie", params={"api_key": TMDB_API_KEY, "query": query})
    results = response.json().get('results', [])

    # Generate clean IDs for each movie result
    for result in results:
        result['clean_id'] = generate_clean_id(result['title'])

    # Render search results template with directory name
    return render_template('search_results.html', query=query, results=results, directory=directory)
# Route for searching TV shows using TMDb API
@app.route('/search_tv', methods=['GET'])
def search_tv():
    # Decode the URL-encoded query parameter to handle special characters
    query = unquote(request.args.get('query', ''))
    directory = request.args.get('directory', '')  # Get the directory name from the original TV show card click

    # Log the received search query for debugging purposes
    app.logger.info(f"Search TV query received: {query}, Directory: {directory}")

    # Send search request to TMDb API for TV shows, with filters for English-language results
    response = requests.get(f"{BASE_URL}/search/tv", params={
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": False,
        "language": "en-US",
        "page": 1
    })
    results = response.json().get('results', [])

    # Log the number of results returned by the API
    app.logger.info(f"TMDb API returned {len(results)} results for query: {query}")

    # Generate clean IDs for each TV show result for URL and anchor purposes
    for result in results:
        result['clean_id'] = generate_clean_id(result['name'])
        app.logger.info(f"Result processed: {result['name']} -> Clean ID: {result['clean_id']}")

    # Render search results template with TV show results and directory name
    return render_template('search_results.html', query=query, results=results, content_type="tv", directory=directory)

# Route for selecting a movie and displaying available logos
@app.route('/select_movie/<int:movie_id>', methods=['GET'])
def select_movie(movie_id):
    # Get the directory name passed from the search results
    directory = request.args.get('directory', '')

    # Fetch detailed information about the selected movie from TMDb API
    movie_details = requests.get(f"{BASE_URL}/movie/{movie_id}", params={"api_key": TMDB_API_KEY}).json()

    # Extract movie title and generate a clean ID for URL/anchor purposes
    movie_title = movie_details.get('title', '')
    clean_id = generate_clean_id(movie_title)

    app.logger.info(f"Selected movie: {movie_title}, Directory from click: {directory}")

    # Request available logos for the selected movie from TMDb API
    logos = requests.get(f"{BASE_URL}/movie/{movie_id}/images", params={"api_key": TMDB_API_KEY}).json().get('logos', [])

    # Filter logos to include only English language logos
    logos = [logo for logo in logos if logo['iso_639_1'] == 'en']

    # Function to calculate logo resolution for sorting
    def logo_resolution(logo):
        return logo['width'] * logo['height']  # Calculate area of the logo

    # Sort logos by resolution in descending order (highest resolution first)
    logos_sorted = sorted(logos, key=logo_resolution, reverse=True)

    # Format logo details for display, including full URL, dimensions, and language
    formatted_logos = [{
        'url': f"{POSTER_BASE_URL}{logo['file_path']}",
        'size': f"{logo['width']}x{logo['height']}",
        'language': logo['iso_639_1']
    } for logo in logos_sorted]

    # Render logo selection template with sorted logos, movie details, TMDb ID, and DIRECTORY
    return render_template('logo_selection.html', media_title=movie_title, content_type='movie', logos=formatted_logos, tmdb_id=movie_id, directory=directory)

# Route for selecting a TV show and displaying available logos
@app.route('/select_tv/<int:tv_id>', methods=['GET'])
def select_tv(tv_id):
    # Get the directory name passed from the search results
    directory = request.args.get('directory', '')

    # Fetch detailed information about the selected TV show from TMDb API
    tv_details = requests.get(f"{BASE_URL}/tv/{tv_id}", params={"api_key": TMDB_API_KEY}).json()

    # Extract TV show title and generate a clean ID for URL/anchor purposes
    tv_title = tv_details.get('name', '')
    clean_id = generate_clean_id(tv_title)

    app.logger.info(f"Selected TV show: {tv_title}, Directory from click: {directory}")

    # Request available logos for the selected TV show from TMDb API
    logos = requests.get(f"{BASE_URL}/tv/{tv_id}/images", params={"api_key": TMDB_API_KEY}).json().get('logos', [])

    # Filter logos to include only English language logos
    logos = [logo for logo in logos if logo['iso_639_1'] == 'en']

    # Sort logos by resolution in descending order (highest resolution first)
    logos_sorted = sorted(logos, key=lambda p: p['width'] * p['height'], reverse=True)

    # Format logo details for display, including full URL, dimensions, and language
    formatted_logos = [{
        'url': f"{POSTER_BASE_URL}{logo['file_path']}",
        'size': f"{logo['width']}x{logo['height']}",
        'language': logo['iso_639_1']
    } for logo in logos_sorted]

    # Render logo selection template with sorted logos, TV show details, content type, TMDb ID, and DIRECTORY
    return render_template('logo_selection.html', logos=formatted_logos, media_title=tv_title, clean_id=clean_id, content_type="tv", tmdb_id=tv_id, directory=directory)

# Function to handle logo download and thumbnail creation
def save_logo_and_thumbnail(logo_url, movie_title, save_dir):
    # Define full paths for the logo and thumbnail (PNG to preserve transparency)
    full_logo_path = os.path.join(save_dir, 'logo.png')
    thumb_logo_path = os.path.join(save_dir, 'logo-thumb.png')

    try:
        # Remove any existing logo files in the directory
        for ext in ['jpg', 'jpeg', 'png']:
            existing_logo = os.path.join(save_dir, f'logo.{ext}')
            existing_thumb = os.path.join(save_dir, f'logo-thumb.{ext}')
            if os.path.exists(existing_logo):
                os.remove(existing_logo)
            if os.path.exists(existing_thumb):
                os.remove(existing_thumb)

        # Download the full-resolution logo from the URL
        response = requests.get(logo_url)
        if response.status_code == 200:
            # Save the downloaded logo image
            with open(full_logo_path, 'wb') as file:
                file.write(response.content)

            # Create a thumbnail using Pillow image processing library
            with Image.open(full_logo_path) as img:
                # Logos are typically wider than tall, so we'll maintain aspect ratio
                # and resize to a max width of 500px
                max_width = 500
                aspect_ratio = img.width / img.height

                # Calculate thumbnail dimensions maintaining aspect ratio
                if img.width > max_width:
                    new_width = max_width
                    new_height = int(max_width / aspect_ratio)
                else:
                    new_width = img.width
                    new_height = img.height

                # Resize the image with high-quality Lanczos resampling
                img_resized = img.resize((new_width, new_height), Image.LANCZOS)

                # Save the thumbnail image as PNG to preserve transparency
                img_resized.save(thumb_logo_path, "PNG", optimize=True)

            print(f"Logo and thumbnail saved successfully for '{movie_title}'")
            return full_logo_path  # Return the local path where the logo was saved
        else:
            print(f"Failed to download logo for '{movie_title}'. Status code: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error saving logo and generating thumbnail for '{movie_title}': {e}")
        return None

# Route for handling logo selection and downloading
@app.route('/select_logo', methods=['POST'])
def select_logo():
    # Log the received form data for debugging and tracking
    app.logger.info("Received form data: %s", request.form)

    # Validate that all required form data is present
    if 'logo_path' not in request.form or 'media_title' not in request.form or 'media_type' not in request.form:
        app.logger.error("Missing form data: %s", request.form)
        return "Bad Request: Missing form data", 400

    try:
        # Extract form data for logo download
        logo_url = request.form['logo_path']
        media_title = request.form['media_title']
        media_type = request.form['media_type']  # Should be either 'movie' or 'tv'
        tmdb_id = request.form.get('tmdb_id')  # Get TMDb ID if available
        directory = request.form.get('directory', '')  # Get the directory name from the original card click!

        # Log detailed information about the logo selection
        app.logger.info(f"Logo Path: {logo_url}, Media Title: {media_title}, Media Type: {media_type}, TMDb ID: {tmdb_id}, Directory: {directory}")

        # Select base folders based on media type (movies or TV shows)
        base_folders = movie_folders if media_type == 'movie' else tv_folders

        # Initialize variables for directory matching
        save_dir = None
        possible_dirs = []
        best_similarity = 0
        best_match_dir = None

        # FIRST: If we have the directory name from the original click, use it directly!
        if directory:
            # Find the exact directory in the base folders
            for base_folder in base_folders:
                potential_path = os.path.join(base_folder, directory)
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    save_dir = potential_path
                    app.logger.info(f"Using directory from original click: {save_dir}")
                    # Save the TMDb ID mapping for future use
                    if tmdb_id:
                        save_mapped_directory(tmdb_id, media_type, save_dir)
                    # Save the logo
                    local_logo_path = save_logo_and_thumbnail(logo_url, media_title, save_dir)
                    if local_logo_path:
                        message = f"Logo for '{media_title}' has been downloaded!"
                        send_slack_notification(message, local_logo_path, logo_url)
                    return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # SECOND: Check if we have a saved mapping for this TMDb ID
        if tmdb_id:
            mapped_dir = get_mapped_directory(tmdb_id, media_type)
            if mapped_dir:
                app.logger.info(f"Using previously saved directory mapping for {media_type}_{tmdb_id}: {mapped_dir}")
                save_dir = mapped_dir
                # Skip the fuzzy matching logic and go straight to saving
                local_logo_path = save_logo_and_thumbnail(logo_url, media_title, save_dir)
                if local_logo_path:
                    message = f"Logo for '{media_title}' has been downloaded!"
                    send_slack_notification(message, local_logo_path, logo_url)
                return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # Normalize media title for comparison
        normalized_media_title = normalize_title(media_title)

        # Search for an exact or closest matching directory
        for base_folder in base_folders:
            directories = os.listdir(base_folder)
            possible_dirs.extend(directories)

            for directory in directories:
                normalized_dir_name = normalize_title(directory)
                # Calculate string similarity between media title and directory name
                similarity = SequenceMatcher(None, normalized_media_title, normalized_dir_name).ratio()

                # Log the comparison for debugging
                app.logger.info(f"Comparing '{media_title}' (normalized: '{normalized_media_title}') with directory '{directory}' (normalized: '{normalized_dir_name}'). Similarity: {similarity:.3f}")

                # Update best match if current similarity is higher
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_dir = os.path.join(base_folder, directory)
                    app.logger.info(f"New best match: '{directory}' with similarity {similarity:.3f}")

                # Check for exact match (case-insensitive and normalized)
                if normalized_media_title == normalized_dir_name:
                    save_dir = os.path.join(base_folder, directory)
                    app.logger.info(f"Exact match found: '{directory}'")
                    break

            if save_dir:
                break

        # Log final matching result
        app.logger.info(f"Best similarity: {best_similarity:.3f}, Best match dir: {best_match_dir}, Exact match dir: {save_dir}")

        # If an exact match is found, proceed with downloading
        if save_dir:
            # Save the TMDb ID mapping for future use
            if tmdb_id:
                save_mapped_directory(tmdb_id, media_type, save_dir)

            local_logo_path = save_logo_and_thumbnail(logo_url, media_title, save_dir)
            if local_logo_path:
                # Send Slack notification about successful logo download
                message = f"Logo for '{media_title}' has been downloaded!"
                send_slack_notification(message, local_logo_path, logo_url)
            return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # If no exact match, use best similarity match above a threshold
        # Increased threshold to 0.9 to prevent false matches between similar titles
        similarity_threshold = 0.9
        if best_similarity >= similarity_threshold:
            app.logger.info(f"Using best match '{best_match_dir}' (similarity: {best_similarity:.3f})")
            save_dir = best_match_dir

            # Save the TMDb ID mapping for future use
            if tmdb_id:
                save_mapped_directory(tmdb_id, media_type, save_dir)

            local_logo_path = save_logo_and_thumbnail(logo_url, media_title, save_dir)
            if local_logo_path:
                # Send Slack notification about successful logo download
                message = f"Logo for '{media_title}' has been downloaded!"
                send_slack_notification(message, local_logo_path, logo_url)
            return redirect(url_for('tv_shows' if media_type == 'tv' else 'index') + f"#{generate_clean_id(media_title)}")

        # If no suitable directory found, present user with directory selection options
        similar_dirs = get_close_matches(media_title, possible_dirs, n=5, cutoff=0.5)
        return render_template('select_directory.html', similar_dirs=similar_dirs, media_title=media_title, logo_path=logo_url, media_type=media_type, tmdb_id=tmdb_id)

    except FileNotFoundError as fnf_error:
        # Log and handle file not found errors
        app.logger.error("File not found: %s", fnf_error)
        return "Directory not found", 404
    except Exception as e:
        # Log and handle any unexpected errors
        app.logger.exception("Unexpected error in select_logo route: %s", e)
        return "Internal Server Error", 500

# Route for serving logos from the file system
@app.route('/logo/<path:filename>')
def serve_logo(filename):
    # Combine movie and TV folders to search both sets of paths
    base_folders = movie_folders + tv_folders

    # Check if a "refresh" flag is present in the URL query parameters
    refresh = request.args.get('refresh', 'false')
    for base_folder in base_folders:
        full_path = os.path.join(base_folder, filename)
        # Skip Synology NAS special directories
        if '@eaDir' in full_path:
            continue
        if os.path.exists(full_path):
            # Serve the file from the appropriate directory
            response = send_from_directory(base_folder, filename)
            if refresh == 'true':
                # If refresh is requested, set no-cache headers
                response.cache_control.no_cache = True
                response.cache_control.must_revalidate = True
                response.cache_control.max_age = 0
            else:
                # Set long-term caching for efficiency
                response.cache_control.max_age = 31536000  # 1 year in seconds
            return response

    # Log an error if the file is not found
    app.logger.error(f"File not found for {filename} in any base folder.")
    return "File not found", 404

# Route for manually confirming the directory and saving the logo
@app.route('/confirm_directory', methods=['POST'])
def confirm_directory():
    # Extract form data for manual logo directory selection
    selected_directory = request.form.get('selected_directory')
    movie_title = request.form.get('media_title')
    logo_url = request.form.get('logo_path')
    content_type = request.form.get('media_type', 'movie')  # Use 'media_type' to match the form field
    tmdb_id = request.form.get('tmdb_id')  # Get TMDb ID if available

    # Log all received form data for debugging
    app.logger.info(f"Received data: selected_directory={selected_directory}, movie_title={movie_title}, logo_url={logo_url}, content_type={content_type}, tmdb_id={tmdb_id}")

    # Validate form data
    if not selected_directory or not movie_title or not logo_url:
        app.logger.error("Missing form data: selected_directory=%s, media_title=%s, logo_url=%s",
                         selected_directory, movie_title, logo_url)
        return "Bad Request: Missing form data", 400

    # Find the correct base folder for the selected directory
    save_dir = None
    base_folders = movie_folders if content_type == 'movie' else tv_folders

    for base_folder in base_folders:
        if selected_directory in os.listdir(base_folder):
            save_dir = os.path.join(base_folder, selected_directory)
            break

    if not save_dir:
        # Log an error if directory not found
        app.logger.error(f"Selected directory '{selected_directory}' not found in base folders.")
        return "Directory not found", 404

    # Save the TMDb ID mapping for future use (this is the key part - remember this selection!)
    if tmdb_id:
        save_mapped_directory(tmdb_id, content_type, save_dir)
        app.logger.info(f"Saved mapping for future: {content_type}_{tmdb_id} -> {save_dir}")

    # Save the logo and get the local path
    local_logo_path = save_logo_and_thumbnail(logo_url, movie_title, save_dir)
    if local_logo_path:
        # Send Slack notification about successful download
        message = f"Logo for '{movie_title}' has been downloaded!"
        send_slack_notification(message, local_logo_path, logo_url)
        app.logger.info(f"Logo successfully saved to {local_logo_path}")
    else:
        app.logger.error(f"Failed to save logo for '{movie_title}'")
        return "Failed to save logo", 500

    # Generate clean ID for navigation anchor
    anchor = generate_clean_id(movie_title)

    # Determine redirect URL based on content type
    redirect_url = url_for('index') if content_type == 'movie' else url_for('tv_shows')

    # Log the redirect URL for verification
    app.logger.info(f"Redirect URL: {redirect_url}#{anchor}")

    return redirect(f"{redirect_url}#{anchor}")

# Function to send Slack notifications about logo downloads
def send_slack_notification(message, local_logo_path, logo_url):
    # Retrieve Slack webhook URL from environment variables
    slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if slack_webhook_url:
        # Prepare Slack payload with message and logo details
        payload = {
            "text": message,
            "attachments": [
                {
                    "text": f"Logo saved to: {local_logo_path}",
                    "image_url": logo_url  # Display original TMDb logo in Slack
                }
            ]
        }
        try:
            # Send notification to Slack
            response = requests.post(slack_webhook_url, json=payload)
            if response.status_code == 200:
                print(f"Slack notification sent successfully for '{local_logo_path}'")
            else:
                print(f"Failed to send Slack notification. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error sending Slack notification: {e}")
    else:
        print("Slack webhook URL not set.")

# Alternative route for page refresh
@app.route('/refresh')
def refresh_page():
    return redirect(url_for('index', refresh='true'))

# Main entry point for running the Flask application
if __name__ == '__main__':
    # Start the app, listening on all network interfaces at port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)