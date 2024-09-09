# Base image with Python (multi-architecture support is native here)
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements first to leverage Docker's caching mechanism for dependencies
COPY requirements.txt /app/

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Pillow in the container (could be part of requirements.txt, but included separately here)
RUN pip install Pillow

# Copy the rest of the app
COPY . /app

# Expose the port that Flask runs on
EXPOSE 5000

# Define the command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0"]