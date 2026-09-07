import os
import socket
import time

from flask import Flask, render_template
import redis

app = Flask(__name__)

# --- Environment variables -------------------------------------------------
# These are set in docker-compose.yml (via `environment:`) or in the .env
# file. Change them and re-run `docker compose up` to see them take effect
# WITHOUT touching a single line of this code.
APP_NAME = os.environ.get("APP_NAME", "Docker Study App")
APP_COLOR = os.environ.get("APP_COLOR", "#2563eb")
APP_ENV = os.environ.get("APP_ENV", "development")
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# --- Connect to the redis service --------------------------------------
# "redis" below resolves via Docker's internal DNS -- it's the *service
# name* from docker-compose.yml, not localhost. This is the main thing to
# study: containers talk to each other by service name over a shared
# network that Compose creates automatically.
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_visit_count():
    """Increment and return a persistent counter stored in Redis.

    Try killing/restarting the web container: the count survives, because
    it lives in Redis (and Redis's data lives in a named volume). Then try
    `docker compose down -v` and start again: the count resets, because -v
    also removes volumes.
    """
    for attempt in range(5):
        try:
            return r.incr("visits")
        except redis.exceptions.ConnectionError:
            time.sleep(1)
    return "N/A (redis unreachable)"


@app.route("/")
def index():
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_color=APP_COLOR,
        app_env=APP_ENV,
        hostname=socket.gethostname(),
        visits=get_visit_count(),
        redis_host=REDIS_HOST,
        redis_port=REDIS_PORT,
    )


@app.route("/health")
def health():
    return {"status": "ok"}, 200

@app.route("/workflow")
def workflow():
    return {"status": "workflow tested successfully"}, 200

@app.route("/test")
def test():
    return {"status": "testing"}, 200

@app.route("/test1")
def test1():
    return {"status": "testing1"}, 200

if __name__ == "__main__":
    # host=0.0.0.0 is required -- 127.0.0.1 would only be reachable from
    # inside the container, not from your host machine's browser.
    app.run(host="0.0.0.0", port=5000)
