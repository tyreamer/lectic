# Always-on Lectic: the same server `lectic share` runs, on a host that never sleeps.
# Knowledge lives on the volume at /data; set LECTIC_TOKEN to choose the secret, or let it be generated once.
FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir /app yt-dlp
ENV LECTIC_HOME=/data
# YouTube throttles datacenter networks. Give the container a route it accepts:
#   -e LECTIC_YTDLP_PROXY=http://user:pass@host:port      (a residential proxy)
#   -e LECTIC_YTDLP_COOKIES=/data/cookies.txt              (exported from a signed-in browser)
VOLUME /data
EXPOSE 8787
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health')" || exit 1
CMD ["lectic", "serve", "--http", "--host", "0.0.0.0", "--port", "8787"]
