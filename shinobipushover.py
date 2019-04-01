#!/usr/bin/env python3
from datetime import datetime, timedelta
from dateutil import tz
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
import logging
import os
import re
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
TIMEDELTA_MINUTES = os.getenv("TIMEDELTA_MINUTES") or 5

application = Flask("shinobipushover")
application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///notifications.db"
database = SQLAlchemy(application)

logging.basicConfig(level=logging.INFO)

def utc_strptime(s):
	# colon was only allowed in timezone offset from Python 3.7
	safe_tz = re.sub(r'\+(\d+):(\d+)', r'+\1\2', s)
	return datetime.strptime(safe_tz, "%Y-%m-%dT%H:%M:%S%z").astimezone(tz.tzutc())

class Monitor(database.Model):
	id = database.Column(database.String(30), primary_key=True)
	name = database.Column(database.String(30))
	last_note = database.Column(database.DateTime)


class Video:
	"""
	Capture the interesting fields from a Video JSON blob
	"""
	def __init__(self, video):
		self.time = utc_strptime(video["time"])
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
	logging.info("GET JSON (args=%s, kwargs=%s)", str(args), str(kwargs))
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
	logging.info("GET binary (args=%s, kwargs=%s)", str(args), str(kwargs))
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
		zero_time = datetime.fromtimestamp(0).astimezone(tz.tzutc())
		monitor = Monitor(id=monitor_id, name=name, last_note=zero_time)
		database.session.add(monitor)
	return monitor


def load_snapshot_image(path, monitor_id):
	try:
		with open(path, 'rb') as f:
			return f.read()
	except Exception as e:
		logging.info("failed to load %s: %s; falling back to current snapshot", path, e)
		# fallback to a current snapshot from the indicated monitor
		return shinobi_get_binary(f"{INTERNAL_URL}/{API_KEY}/jpeg/{GROUP_KEY}/{monitor_id}/s.jpg")


def notify(monitor, video, snapshot):
	"""
	Send a push notification for a given video
	"""
	local_time = video.time.astimezone(tz.tzlocal())
	response = requests.post('https://api.pushover.net/1/messages.json', params={
		'token': PUSHOVER_TOKEN,
		'user':  PUSHOVER_USER,
		'title': "Motion alert",
		'message': f"Motion detected by {monitor.name} camera at {local_time.strftime('%H:%M:%S on %d %B %Y')}",
		'sound': 'none',
		'url': video.href
	}, files={
		'attachment': snapshot
	})
	return response.json() if response.status_code < 300 else response.status_code


@application.route("/event/<monitor_id>")
def event(monitor_id):
	"""
	Shinobi Webhook for a new event. Fetches unwatched videos for the given monitor
	and sends push notifications for each event.
	"""
	videos = shinobi_get_videos(monitor_id, datetime.now() - timedelta(minutes=int(TIMEDELTA_MINUTES))).get("videos", [])
	if len(videos) == 0:
		return "No videos"

	monitor = monitor_by_id(monitor_id)
	earliest_note = monitor.last_note + timedelta(minutes=5)

	snapshot = load_snapshot_image(request.args.get("snapshot"), monitor_id)

	for video_json in videos:
		video = Video(video_json)
		if video.is_unread and video.time > earliest_note:
			notify(monitor, video, snapshot)
			shinobi_get_json(video.change_to_read)
			monitor.last_note = video.time

	database.session.commit()
	return "ok"


if __name__ == "__main__":
	if 'initdb' in sys.argv:
		database.create_all()
	else:
		application.run("0.0.0.0", port=5000, debug=True)
