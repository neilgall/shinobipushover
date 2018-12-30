#!/usr/bin/env python3
from datetime import datetime, timedelta
from flask import Flask
import os
import requests

EXTERNAL_URL = os.getenv("SHINOBI_EXTERNAL_URL")
INTERNAL_URL = os.getenv("SHINOBI_INTERNAL_URL")
API_KEY = os.getenv("SHINOBI_API_KEY")
GROUP_KEY = os.getenv("SHINOBI_GROUP_KEY")
USER_EMAIL = os.getenv("SHINOBI_USER_EMAIL")
USER_PASS = os.getenv("SHINOBI_USER_PASS")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER = os.getenv("PUSHOVER_USER")

application = Flask("shinobipushover")

def shinobi_login():
	"""
	Login to Shinobi to enable access to the API
	"""
	login = requests.post(f"{BASE_URL}?json=true", json={
		"machineId": "pushover",
		"mail": USER_EMAIL,
		"pass": USER_PASS,
		"function": "dash"
	}).json()
	return login.get("ok") == True

def shinobi_get_json(*args, **kwargs):
	"""
	Attempt a GET request to the Shinobi API. If this fails due to authorisation, a
	login is performed and the GET is requested again.
	"""
	result = requests.get(*args, **kwargs).json()
	if type(result) is not dict or result.get("msg") != "Not Authorized":
		return result
	elif shinobi_login():
		return requests.get(*args, **kwargs).json()
	else:
		raise ConnectionRefusedError(result.text)

def shinobi_get_binary(*args, **kwargs):
	"""
	Get data from a Shinobi API with no processing. Must be logged in
	"""
	return requests.get(*args, **kwargs).data

def shinobi_get_monitor_name_by_id(id):
	"""
	Given a monitor ID, fetch its human-readable name
	"""
	monitors = shinobi_get_json(f"{INTERNAL_URL}/{API_KEY}/monitor/{GROUP_KEY}")
	return next(m["name"] for m in monitors if m["mid"] == id)

def shinobi_get_videos(monitor, start_datetime):
	"""
	Get the videos for a given monitor ID since the provided start datetime
	"""
	start = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
	return shinobi_get_json(f"{INTERNAL_URL}/{API_KEY}/videos/{GROUP_KEY}/{monitor}?start={start}")

def notify(monitor, time, shapshot, url):
	"""
	Send a push notification for a given monitor (provide the human-readable name) and
	timestamp (a datetime), with an image snapshot and a link to the video URL
	"""
	response = requests.post('https://api.pushover.net/1/messages.json', params={
		'token': PUSHOVER_TOKEN,
		'user':  PUSHOVER_USER,
		'title': "Motion alert",
		'message': f"Motion detected by {monitor} camera at {time.strftime('%H:%M:%S on %d %B %Y')}",
		'sound': 'none',
		'url': url
	}, files={
		'attachment': snapshot
	})
	return response.json() if response.status_code < 300 else response.status_code

def process_event(monitor, video):
	"""
	Do all processing for a given monitor and video
	"""
	time = datetime.strptime(video["time"], "%Y-%m-%dT%H:%M:%SZ")
	href = f"{EXTERNAL_URL}{video['href']}"
	notify(monitor_name, time, href)

	mark_read = f"{INTERNAL_URL}{video['links']['changeToRead']}"
	shinobi_get_json(mark_read)


@application.route("/event/<monitor>")
def event(monitor, shapshot):
	"""
	Shinobi Webhook for a new event. Fetches unwatched videos for the given monitor
	and sends push notifications for each event.
	"""
	videos = shinobi_get_videos(monitor, datetime.now() - timedelta(minutes=5)).get("videos", [])
	if len(videos) == 0:
		return "No videos"

	snapshot = shinobi_get_binary(f"{INTERNAL_URL}/{API_KEY}/jpeg/{GROUP_KEY}/{monitor}/s.jpg")
	monitor_name = shinobi_get_monitor_name_by_id(monitor)
	results = (process_event(video) for video in videos if video['status'] == 1)
	return f"{len(results)} videos processed"

if __name__ == "__main__":
	application.run("0.0.0.0", port=5000, debug=True)
