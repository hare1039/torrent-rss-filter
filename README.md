# torrent-rss-filter

A simple RSS filter: 
It reads from RSS torrent sources, filter by wanted keyword & remove unwanted keyword, and save as new rss feed.

Currently you need to change the RSS source directly in the code, but its fairly simple.

# Setup
To setup, prepare:
- keyword.txt like this (I use regex):
```
.*Baha.*
.*ストライク・ザ・ブラッド.*
(?i).*Strike the Blood IV.*
```

- unwanted-keyword.txt like this:
```
.*NC-Raws.*
```

To register feeds sources, edit main() function:
```
    rss.regisiter(url="https://nyaa.si/?page=rss",
                  saveas="static/nyaa.xml",
                  httpheader={},
                  rss_type="nyaa")
    rss.regisiter(url="http://dl-zip.com/feed/",
                  saveas="static/dl-zip.xml",
                  httpheader={},
                  rss_type="basic")
```
`nyaa` is torrent feed, and `basic` is a normal feed.


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
