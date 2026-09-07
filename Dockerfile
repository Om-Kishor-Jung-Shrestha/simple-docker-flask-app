# syntax=docker/dockerfile:1

# --- Base image ---------------------------------------------------------
# python:3.12-slim is small but still has apt/pip available, unlike
# alpine (which uses musl and can trip up some Python wheels).
FROM python:3.12-slim

# --- Metadata / working directory ---------------------------------------
WORKDIR /app

# --- Environment variables baked into the image -------------------------
# ENV sets a default. It can still be overridden later at `docker run`
# time with -e, or by docker-compose.yml's `environment:` / `env_file:`.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_NAME="Docker Study App"
ENV APP_COLOR="#2563eb"
ENV APP_ENV="development"

# --- Dependency layer -----------------------------------------------------
# Copy ONLY requirements.txt first, then install. Because Docker caches
# layers, this means `docker build` will skip re-installing packages on
# every rebuild unless requirements.txt itself changes -- app.py can
# change freely without invalidating this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application code -----------------------------------------------------
COPY . .

# --- Run as non-root (security best practice) ------------------------------
RUN useradd -m appuser
USER appuser

# --- Document the port the app listens on ----------------------------------
# EXPOSE is documentation only -- it does NOT publish the port to your
# host. That's done by `-p` on `docker run` or `ports:` in Compose.
EXPOSE 5000

# --- Healthcheck ------------------------------------------------------------
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:5000/health')" || exit 1

CMD ["python", "app.py"]
