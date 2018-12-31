#!/usr/bin/env python3
from datetime import datetime, timedelta
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import sys

EXTERNAL_URL = os.getenv("SHINOBI_EXTERNAL_URL")
INTERNAL_URL = os.getenv("SHINOBI_INTERNAL_URL") or EXTERNAL_URL
API_KEY = os.getenv("SHINOBI_API_KEY")
GROUP_KEY = os.getenv("SHINOBI_GROUP_KEY")
USER_EMAIL = os.getenv("SHINOBI_USER_EMAIL")
USER_PASS = os.getenv("SHINOBI_USER_PASS")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER = os.getenv("PUSHOVER_USER")

application = Flask("shinobipushover")
application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///notifications.db"
database = SQLAlchemy(application)

class Monitor(database.Model):
	id = database.Column(database.String(30), primary_key=True)
	name = database.Column(database.String(30))
	last_note = database.Column(database.DateTime)


class Video:
	"""
	Capture the interesting fields from a Video JSON blob
	"""
	def __init__(self, monitor, snapshot, video):
		self.monitor = monitor
		self.snapshot = snapshot
		self.time = datetime.strptime(video["time"], "%Y-%m-%dT%H:%M:%SZ")
		self.href = f"{EXTERNAL_URL}{video['href']}"
		self.change_to_read = f"{INTERNAL_URL}{video['links']['changeToRead']}"
		self.is_unread = video['status'] == 1


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
	print("GET JSON", *args, **kwargs)
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
	print("GET binary", *args, **kwargs)
	return requests.get(*args, **kwargs).content

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

def monitor_by_id(monitor_id):
	"""
	Get the Monitor record for a monitor ID. If it does not exist in the database, query the
	information from the Shinobi API and create the record.
	"""
	monitor = Monitor.query.filter_by(id=monitor_id).first()
	if monitor is None:
		name = shinobi_get_monitor_name_by_id(monitor_id)
		monitor = Monitor(id=monitor_id, name=name, last_note=datetime.fromordinal(1))
	return monitor

def notify(video, snapshot):
	"""
	Send a push notification for a given video
	"""
	response = requests.post('https://api.pushover.net/1/messages.json', params={
		'token': PUSHOVER_TOKEN,
		'user':  PUSHOVER_USER,
		'title': "Motion alert",
		'message': f"Motion detected by {video.monitor.name} camera at {video.time.strftime('%H:%M:%S on %d %B %Y')}",
		'sound': 'none',
		'url': video.href
	}, files={
		'attachment': snapshot
	})
	return response.json() if response.status_code < 300 else response.status_code


def process_event(video):
	"""
	For a given Video, fetch the snapshot from Shinobi, send the push notification,
	mark the video as read (so it doesn't get processed again), and update the local
	database.
	"""
	snapshot = shinobi_get_binary(f"{INTERNAL_URL}{video.snapshot}")
	notify(video, snapshot)

	shinobi_get_json(video.change_to_read)

	monitor.last_note = video.time
	database.session.commit()


@application.route("/event/<monitor_id>")
def event(monitor_id):
	"""
	Shinobi Webhook for a new event. Fetches unwatched videos for the given monitor
	and sends push notifications for each event.
	"""
	videos = shinobi_get_videos(monitor_id, datetime.now() - timedelta(minutes=50)).get("videos", [])
	if len(videos) == 0:
		return "No videos"

	monitor = monitor_by_id(monitor_id)
	snapshot = request.args.get("snapshot") or f"/{API_KEY}/jpeg/{GROUP_KEY}/{monitor_id}/s.jpg"

	for video_json in videos:
		video = Video(monitor, snapshot, video_json)
		if video.is_unread and video.time > monitor.last_note:
			process_event(video)

	return "ok"


if __name__ == "__main__":
	if 'initdb' in sys.argv:
		database.create_all()
	else:
		application.run("0.0.0.0", port=5000, debug=True)
