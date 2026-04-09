from services.thingspeak_service import fetch_latest_feeds, fetch_last_feed

try:
    feeds = fetch_latest_feeds()
    print('history_count=', len(feeds))
    if feeds:
        print('first=', feeds[0])
        print('last=', feeds[-1])
except Exception as e:
    print('fetch_latest_feeds error:', repr(e))

try:
    latest = fetch_last_feed()
    print('latest=', latest)
except Exception as e:
    print('fetch_last_feed error:', repr(e))
