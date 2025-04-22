# Use Alpine as the base image
FROM alpine:latest

# Install Python, pip, and other dependencies
RUN apk add --no-cache python3 py3-pip

# Set the working directory
WORKDIR /usr/src/app

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy application files
COPY . .

# Expose the application's port
EXPOSE 5000

# Run the application
CMD ["python3", "app.py"]