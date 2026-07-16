# Step 1: Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Copy only the requirements first to leverage Docker's cache layer
COPY requirements.txt .

# Step 4: Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy the rest of the application code
COPY . .

# Step 6: Expose the port the app runs on (Render overrides this, but it's good practice)
EXPOSE 8080

# Step 7: Define the command to run your app
# Ensure your app binds to 0.0.0.0 so Render can route external traffic to it
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]