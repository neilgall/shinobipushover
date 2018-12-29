#!/usr/bin/env python3
from flask import Flask
import requests

app = Flask("shinobipushover")

@app.route("/event/<monitor>")
def event(monitor):
	pass

if __name__ == "__main__":
	app.run("0.0.0.0", port=5000, debug=True)
