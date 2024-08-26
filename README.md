# Posterr
🎬 Posterr: (Partially)Automate your movie poster collection! Posterr is a Flask app that scrapes movie directories and downloads high-quality posters from TheMovieDB. Designed for seamless integration with Docker on Synology NAS. Optional Slack integration for instant notifications!

Welcome to Posterr, a Flask-based application designed to automatically scrape your movie directories and download high-quality posters from TheMovieDB (TMDb). Whether you’re managing a vast movie collection on your Synology NAS or simply want to keep your movie library visually appealing, Posterr is here to help. Additionally, you can opt-in for Slack notifications to get instant updates when new posters are added!

## Features

	•	Automated Poster Downloading: Automatically fetch posters from TMDb based on your movie directory.
	•	Multi-Directory Support: Seamlessly manage multiple movie directories.
	•	Slack Integration (Optional): Get notified instantly in your Slack channel when a poster is downloaded.
	•	Docker Compatible: Built with Docker in mind, especially for Synology NAS.

## Prerequisites

	•	Docker installed on your system.
	•	A Synology NAS or any system capable of running Docker containers.
	•	A valid TMDb API key.
	•	(Optional) Slack webhook URL for notifications.

## Getting Started

## 1. Clone the Repository:
```
git clone https://github.com/anthonysnyder/posterr.git
cd posterr
```
## 2. Setup Docker Compose:
Create a docker-compose.yml file in the root directory of the project:
```
version: '3.8'

services:
  posterr:
    image: swguru2004/posterr:latest
    container_name: posterr
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
Open your browser and go to http://localhost:5000 or your NAS IP to start using Posterr.

## Slack Integration (Optional)

To enable Slack notifications, add your Slack Webhook URL in the SLACK_WEBHOOK_URL environment variable in the docker-compose.yml file.
```
environment:
  - SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
```
Feel free to fork the repo and submit pull requests. Your contributions are welcome!

License

This project is licensed under the MIT License. See the LICENSE file for more details.

For more details, visit the [Posterr GitHub Repository](https://github.com/anthonysnyder/posterr/).
