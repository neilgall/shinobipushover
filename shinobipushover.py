#!/usr/bin/env python3
from datetime import datetime, timedelta
from flask import Flask
import os
import requests

BASE_URL = os.getenv("SHINOBI_BASE_URL")
API_KEY = os.getenv("SHINOBI_API_KEY")
GROUP_KEY = os.getenv("SHINOBI_GROUP_KEY")
USER_EMAIL = os.getenv("SHINOBI_USER_EMAIL")
USER_PASS = os.getenv("SHINOBI_USER_PASS")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER = os.getenv("PUSHOVER_USER")

application = Flask("shinobipushover")

def shinobi_login():
	login = requests.post(f"{BASE_URL}?json=true", json={
		"machineId": "puhsover",
		"mail": USER_EMAIL,
		"pass": USER_PASS,
		"function": "dash"
	}).json()
	return login.get("ok") == True

def shinobi_get_json(*args, **kwargs):
	result = requests.get(*args, **kwargs).json()
	if type(result) is not dict or result.get("msg") != "Not Authorized":
		return result
	elif shinobi_login():
		return requests.get(*args, **kwargs).json()
	else:
		raise ConnectionRefusedError(result.text)

def shinobi_get_monitor_name_by_id(id):
	monitors = shinobi_get_json(f"{BASE_URL}/{API_KEY}/monitor/{GROUP_KEY}")
	return next(m["name"] for m in monitors if m["mid"] == id)

def shinobi_get_videos(monitor, start_datetime):
	start = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
	return shinobi_get_json(f"{BASE_URL}/{API_KEY}/videos/{GROUP_KEY}/{monitor}?start={start}")

def notify(monitor, time, url):
    response = requests.post('https://api.pushover.net/1/messages.json', params={
        'token': PUSHOVER_TOKEN,
        'user':  PUSHOVER_USER,
        'title': "Motion alert",
        'message': f"Motion detected by {monitor} camera at {time.strftime('%H:%M:%S on %d %B %Y')}",
        'sound': 'none',
        'url': url
    })
    return response.json() if response.status_code < 300 else response.status_code

@application.route("/event/<monitor>")
def event(monitor):
	videos = shinobi_get_videos(monitor, datetime.now() - timedelta(minutes=50)).get("videos", [])
	if len(videos) == 0:
		return "No videos"
	monitor_name = shinobi_get_monitor_name_by_id(monitor)
	for video in videos:
		time = datetime.strptime(video["time"], "%Y-%m-%dT%H:%M:%SZ")
		action_url = f"{BASE_URL}{video['actionUrl']}"
		notify(monitor_name, time, action_url)
	return f"{len(videos)} videos"

if __name__ == "__main__":
	application.run("0.0.0.0", port=5000, debug=True)
