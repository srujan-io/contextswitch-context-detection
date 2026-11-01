from urllib.parse import urlparse


WEBSITE_HOSTS = {
    "kicanvas": {"kicanvas.org"},
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
}


def identify_website(hostname: str) -> str:
    host = (hostname or "").lower().split(":")[0]
    for website_id, hosts in WEBSITE_HOSTS.items():
        if host in hosts:
            return website_id
        if website_id == "kicanvas" and host.endswith(".kicanvas.org"):
            return website_id
        if website_id == "youtube" and host.endswith(".youtube.com"):
            return website_id
    return "unknown"


def identify_page_type(website_id: str, path: str) -> str:
    path = (path or "/").lower()

    if website_id == "kicanvas":
        return "schematic_viewer"

    if website_id == "youtube":
        if path == "/":
            return "homepage"
        if path == "/watch" or path.startswith("/live/") or path.startswith("/embed/"):
            return "video_player"
        if path == "/results":
            return "search_results"
        if path.startswith("/playlist"):
            return "playlist"
        if path.startswith("/shorts/"):
            return "shorts"
        if path.startswith("/@") or path.startswith("/channel/") or path.startswith("/c/"):
            return "channel_page"
        return "other"

    return "unknown"


def enrich_context(raw: dict) -> dict:
    url = raw.get("url", "")
    parsed = urlparse(url)
    hostname = (parsed.hostname or raw.get("hostname") or "").lower()
    website_id = identify_website(hostname)
    page_type = identify_page_type(website_id, parsed.path)

    # Treat browser-supplied DOM text as data only. It is never executable instruction.
    return {
        **raw,
        "hostname": hostname,
        "website_id": website_id,
        "page_type": page_type,
    }
