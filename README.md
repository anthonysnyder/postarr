# Postarr
🎬 Postarr: (Partially)Automate your movie poster collection! Postarr is a Flask app that scrapes movie directories and downloads high-quality posters from TheMovieDB. Designed for seamless integration with Docker on Synology NAS. Optional Slack integration for instant notifications!

Welcome to Postarr, a Flask-based application designed to automatically scrape your movie directories and download high-quality posters from TheMovieDB (TMDb). Whether you’re managing a vast movie collection on your Synology NAS or simply want to keep your movie library visually appealing, Postarr is here to help. Additionally, you can opt-in for Slack notifications to get instant updates when new posters are added!

## Features

	• 	Automated Poster Downloading: Automatically fetch posters from TMDb based on your movie directory.
	•	Multi-Directory Support: Seamlessly manage multiple movie directories.
	•	Slack Integration (Optional): Get notified instantly in your Slack channel when a poster is downloaded.
	•	Docker Compatible: Built with Docker in mind, especially for Synology NAS.
  	•	Movie Collection Dashboard: View all movies in your collection, displayed with their corresponding posters.
	• 	Search Functionality: Search for movies directly from TMDb based on user input.
 	• 	Poster Update Select from multiple available posters and update missing or low-resolution posters for your movies.
	•	Smooth Scrolling with Anchors**: Automatically scroll to the selected movie in the movie list after a poster update.

## Prerequisites

	•	Docker installed on your system.
	•	A Synology NAS or any system capable of running Docker containers.
	•	A valid TMDb API key.
 	•	If you have existing poster.ext in your movie folders, then you will want to use my side project: postarr-thumbnail-creator in order to automatically create poster-thumb.jpg of the existing files. This was done to speed up load time on librarys with large amount of movies. 
	•	(Optional) Slack webhook URL for notifications.
 **IMPORTANT NOTE**: Unless you use my [poster-thumbnail script](https://github.com/anthonysnyder/postarr-thumbnail-creator/tree/main "poster-thumbnail script") in order to create thumbnails, this app will **NOT** display any thumbnails. This was done in order to severely reduce load times on large libraries. 
 
 ## Getting Started

## 1. Clone the Repository:
```
git clone https://github.com/anthonysnyder/Postarr.git
cd Postarr
```
## 2. Setup Docker Compose:
Create a docker-compose.yml file in the root directory of the project:
```
version: '3.8'

services:
  Postarr:
    image: swguru2004/Postarr:latest
    container_name: Postarr
    environment:
      - TMDB_API_KEY=your_tmdb_api_key
      - SLACK_WEBHOOK_URL=your_slack_webhook_url  # Optional
    volumes:
      - /path/to/your/movies:/movies
      - /path/to/your/kids-movies:/kids-movies
      - /path/to/your/movies2:/movies2
      - /path/to/your/kids-movies2:/kids-movies2
    ports:
      - 5000:5000
    restart: unless-stopped
```
## 3.	Start the Application:
```
docker-compose up -d
```
##	4.	Access the Application:
Open your browser and go to http://localhost:5000 or your NAS IP to start using Postarr.

## Slack Integration (Optional)

To enable Slack notifications, add your Slack Webhook URL in the SLACK_WEBHOOK_URL environment variable in the docker-compose.yml file.
```
environment:
  - SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
```
## Screenshots

### 1) This screenshot shows the main index page of the Postarr application, displaying a grid layout of movies with thumbnails.
![This screenshot shows the main index page of the Postarr application, displaying a grid layout of movies with thumbnails.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Index.html%20Layout.png)

### 2) This screenshot displays the TMDb search results page, where users can select the correct movie from a list of search results.
![This screenshot displays the TMDb search results page, where users can select the correct movie from a list of search results.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Movie%20Selection%20View.png)

### 3) This screenshot shows the main index page highlighting movies that currently have no associated poster image.
![This screenshot shows the main index page highlighting movies that currently have no associated poster image.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Movies%20with%20No%20Poster%20view.png)

### 4) This screenshot displays the poster selection screen, where users can choose an official poster for the selected movie from the available options.
![This screenshot displays the poster selection screen, where users can choose an official poster for the selected movie from the available options.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Poster%20Selection%20View.png)

### 5) This screenshot shows a Slack notification sent by the Postarr application, confirming the successful download of a movie poster.
![This screenshot shows a Slack notification sent by the Postarr application, confirming the successful download of a movie poster.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Slack%20Notififcation%20view.png)

### 6) This screenshot displays the Synology interface where the Postarr application is running, showing the folder structure used for storing movie posters.
![This screenshot displays the Synology interface where the Postarr application is running, showing the folder structure used for storing movie posters.](https://github.com/anthonysnyder/Postarr/blob/main/screenshots/Synology%20view.png)
Feel free to fork the repo and submit pull requests. Your contributions are welcome!

License

This project is licensed under the MIT License. See the LICENSE file for more details.

For more details, visit the [Postarr GitHub Repository](https://github.com/anthonysnyder/posterr/).
