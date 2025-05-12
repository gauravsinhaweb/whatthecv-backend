# GitHub Actions Workflows

This directory contains GitHub Actions workflows for the WhatTheCV backend application.

## Workflows

### 1. Keep Backend API Alive (`keep-alive.yml`)

This workflow runs every 10 minutes to ping the backend API, helping to prevent the Fly.io instance from idling out due to inactivity.

**Functionality:**
- Makes a simple HTTP request to the API root endpoint
- Logs the timestamp of each successful ping
- Can be manually triggered via the GitHub Actions UI for testing

### 2. Backend API Health Check (`health-check.yml`)

A more advanced workflow that checks if the API is healthy by verifying the response status code.

**Functionality:**
- Runs every 10 minutes
- Checks if the API returns a 200 status code
- Fails the workflow if a non-200 status is received
- Includes configurable notification options (commented out by default)
- Can be manually triggered via the GitHub Actions UI for testing

## Setup

These workflows are automatically enabled when pushed to the repository. No additional setup is required for basic functionality.

For notification features:
1. Uncomment the notification section in `health-check.yml`
2. Configure the necessary secrets in your GitHub repository settings
3. Adjust notification channels and messages as needed 