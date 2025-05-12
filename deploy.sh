#!/bin/bash
set -e

echo "===> Deploying whatthecv-backend to fly.io <===="

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "flyctl is not installed. Please install it first:"
    echo "curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in
echo "Checking if you're logged in to fly.io..."
if ! flyctl auth whoami &> /dev/null; then
    echo "Please log in to fly.io first:"
    flyctl auth login
fi

# Launch the app if it doesn't exist yet
if ! flyctl status --app whatthecv-backend &> /dev/null; then
    echo "Creating the app on fly.io..."
    flyctl launch --no-deploy
else
    echo "App already exists on fly.io"
fi

# Deploy
echo "Deploying the application..."
flyctl deploy

echo "===> Deployment complete! <===="
echo "Your app should be available at: https://whatthecv-backend.fly.dev" 