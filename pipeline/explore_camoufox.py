#!/usr/bin/env python3
"""Explore camoufox API"""
import requests

api_url = "http://localhost:50844"

print("Exploring camoufox API")
print("="*60)

# Check root endpoint
resp = requests.get(f"{api_url}/")
print(f"Root `/`: {resp.status_code}")
print(f"Response: {resp.text[:500]}")
print()

# Try /sessions
resp = requests.get(f"{api_url}/sessions")
print(f"GET `/sessions`: {resp.status_code}")
print(f"Response: {resp.text[:500]}")
print()

# Try /sessions POST
resp = requests.post(f"{api_url}/sessions")
print(f"POST `/sessions`: {resp.status_code}")
print(f"Response: {resp.text[:500]}")
print()

# Check health/status
resp = requests.get(f"{api_url}/health")
print(f"GET `/health`: {resp.status_code}")
print(f"Response: {resp.text}")
print()

# List sessions
resp = requests.get(f"{api_url}/sessions/list")
print(f"GET `/sessions/list`: {resp.status_code}")
print(f"Response: {resp.text[:500]}")
