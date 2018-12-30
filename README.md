# Shinobi Pushover
This is a simple webhook application for sending [Pushover](https://pushover.net) notifications in response to [Shinobi](https://shinobi.video) motion events.

A command might be simpler to implement but I like to run everything in Docker and keep services isolated, and a webhook meets those needs better. Flask and gunicorn make a web service trivial to do anyway.

The entry point is `event(monitor)`. Shinobi monitors have their webhooks set to `http://pushover:8000/event/{{MONITOR_ID}}`, which passes the monitor ID in the request. Flask decodes that from the URL and passes it as the `monitor` parameter to the event handler.

The event handler works as follows:
1. Fetch all the videos for the indicated monitor ID in the past 5 minutes.
2. Use the Shinobi API to get the human-readable name for the monitor ID
3. For each video marked as unread, generate a push notification, and mark it as read

I don't have a way to get a snapshot appropriate for each video yet, so I'm grabbing an immediate snapshot from the monitor and attaching that to the push notification. If the event is still happening maybe it'll include something interesting?! The linked video is the interesting thing anyway.

I build a Docker container for the service based on alpine-python3, which is nice and small, then run it all in docker-compose. Redacting the API tokens and IDs, the `docker-compose.yml` looks like below. This is why the hostname used in the webhook URL is `pushover`.
```
version: '2'
services:
  shinobi:
    image: shinobidocker_shinobi
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
      - /data/shinobi/config:/config
      - /data/shinobi/videos:/opt/shinobi/videos
      - /data/shinobi/data:/var/lib/mysql
      - /dev/shm/shinobiDockerTemp:/dev/shm/streams
    ports:
      - "8080:8080"

  pushover:
    image: shinobi-pushover
    environment:
      - SHINOBI_INTERNAL_URL=http://shinobi:8080
      - SHINOBI_EXTERNAL_URL=...
      - SHINOBI_API_KEY=...
      - SHINOBI_GROUP_KEY=...
      - SHINOBI_USER_EMAIL=...
      - SHINOBI_USER_PASS=...
      - PUSHOVER_TOKEN=...
      - PUSHOVER_USER=...
    ports:
      - "8081:8000"
```
