import time

# Changes on every process start (each deploy restarts the container), so
# appending it to static URLs forces browsers and CDNs to fetch fresh files.
STATIC_VERSION = str(int(time.time()))


def static_version(request):
    return {"STATIC_VERSION": STATIC_VERSION}
