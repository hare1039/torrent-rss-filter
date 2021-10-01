# torrent-rss-filter

A simple RSS filter: 
It reads from RSS torrent sources, filter by wanted keyword & remove unwanted keyword, and save as new rss feed.

# Setup
To setup, prepare `config.yaml`. Basic structure are defined as:
```
sources:
  -                                                                                                
    url: "https://twitter2rss.nomadic.name/imys_staff?"
    saveas: "static/twitterimys.xml"
    httpheader:
    rss_type: "basic"
  -                                                                                                
    url: "https://nyaa.si/?page=rss"
    saveas: "static/nyaa.xml"
    httpheader:
    rss_type: "nyaa"

filter:
  keywords:                                                                      
    - ".*imys_staff.*"
  unwantedwords:
    - "^RT.*[@].*"
```
note: `nyaa` is torrent feed, and `basic` is a normal feed.


# Running
To run, you can use the buildin http server for serving the feed saved in `./static`
```
python3 serve.py --port 8080
``` 

Or *Recommended* use an external production grade http server like caddy
```
python3 serve.py --no-server;
caddy file-server --root ./static --listen 8080 --browse
```

To see complete options, please use `--help`
```
usage: serve.py [-h] [--db-name DB_NAME] [--gc-duration GC_DURATION]
                [--loop-duration LOOP_DURATION] [--port PORT] [--config CONFIG] [--no-server]

optional arguments:
  -h, --help            show this help message and exit
  --db-name DB_NAME     sqlite3 database file name
  --gc-duration GC_DURATION
                        garbage collection on old entries (days)
  --loop-duration LOOP_DURATION
                        duration of refresh databases (seconds)
  --port PORT           listen port
  --config CONFIG       define keywords and sources
  --no-server           turn off the python http server. Only update rss
  ```
