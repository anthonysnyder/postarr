# Example Dockerfile for a Python/Flask app

# Base image with Python
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Pillow in the container
RUN pip install Pillow

# Expose the port that Flask runs on
EXPOSE 5000

# Define the command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0"]