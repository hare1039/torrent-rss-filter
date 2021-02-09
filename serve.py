#!/usr/bin/python3

import os
import io
import sys
import time
import feedparser
import re
import requests
import sqlite3
import pprint
import feedgen.feed
import datetime
import pytz
import hashlib
import http.server
import socketserver
import threading
import argparse

SCRIPT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_FILE_PATH)

class rss_store:
    def __init__(self, args):
        self.db_name = args.db_name
        self.gc_duration = args.gc_duration * 86400
        self.loop_duration = args.loop_duration
        self.conn = sqlite3.connect(self.db_name,
                                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.subscribed = {}
        self.init_db()

    def __del__(self):
        self.conn.close()

    def init_db(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS rss (date INTEGER,
                                                     title TEXT,
                                                     link TEXT,
                                                     description TEXT,
                                                     size TEXT,
                                                     category TEXT,
                                                     categoryid TEXT,
                                                     infoHash TEXT PRIMARY KEY,
                                                     rss_src TEXT)''')
        self.conn.commit()

    def regisiter(self, url, saveas, header = {}):
        self.subscribed[url] = {
            "lastupdate": self.max_update_time(url),
            "saveas": saveas,
            "header": header
        }

    def write_db(self, rss_list, rss_src):
        c = self.conn.cursor()
        tuples = [(time.mktime(x["published_parsed"]),
                   x["title"],
                   x.get("id", 0),
                   x.get("summary", x["description"]),
                   x.get("nyaa_size", 0),
                   x.get("nyaa_category", "cat"),
                   x.get("nyaa_categoryid", "cat"),
                   x.get("nyaa_infohash", hashlib.sha256(x["title"].encode("utf-8")).hexdigest()),
                   rss_src) for x in rss_list]
        c.executemany("INSERT INTO rss VALUES (?,?,?,?,?,?,?,?,?)", tuples)
        self.conn.commit()

    def view(self):
        c = self.conn.cursor()
        for row in c.execute("SELECT * FROM rss"):
            print(row[1], row[7])
        self.conn.commit()

    def size_db(self):
        c = self.conn.cursor()
        for row in c.execute("SELECT COUNT(*) FROM rss"):
            result = row[0]
        self.conn.commit()
        return result

    def max_update_time(self, rss_src):
        c = self.conn.cursor()
        for row in c.execute("SELECT max(date) FROM rss WHERE rss_src=?", (rss_src, )):
            result = row[0]
        self.conn.commit()
        if result:
            return result
        else:
            return 0

    def filter(self, entries):
        with open("keyword.txt", "r") as f:
            keywords = f.read().splitlines()
            keywords = [{"category": s.split("%", 1)[0] if "%" in s else ".*",
                         "regex":    s.split("%", 1)[1] if "%" in s else s} for s in keywords]

        with open("unwanted-keyword.txt", "r") as f:
            unwanted_keywords = f.read().splitlines()

        filtered = []
        for entry in entries:
            skip = False
            for regex in unwanted_keywords:
                if re.match(regex, entry.title):
                    skip = True

            if not skip:
                for key in keywords:
                    if re.match(key["category"], entry.get("nyaa_category", key["category"])) and (re.match(key["regex"], entry.title)):
                        filtered.append(entry)
                        break

        return filtered

    def delete_old_db_entries(self, limit, rss_src):
        c = self.conn.cursor()
        c.execute("DELETE FROM rss WHERE date<? AND rss_src=?", (limit, rss_src))
        self.conn.commit()

    def update(self):
        for url in self.subscribed:
            try:
                resp = requests.get(url, timeout=30.0, headers=self.subscribed[url]["header"])
            except requests.ReadTimeout:
                continue

            nyaa = feedparser.parse(io.BytesIO(resp.content))

            entries = [x for x in nyaa.entries if time.mktime(x.published_parsed) > self.subscribed[url]["lastupdate"]]
            self.subscribed[url]["lastupdate"] = max([time.mktime(x.published_parsed) for x in nyaa.entries] + [self.subscribed[url]["lastupdate"]])
            filtered = self.filter(entries)

            self.write_db(filtered, url)
            self.delete_old_db_entries(self.subscribed[url]["lastupdate"] - self.gc_duration, url)

            fg = feedgen.feed.FeedGenerator()
            fg.load_extension("torrent", atom=True, rss=True)
            fg.id(url)
            fg.title("Filtered torrent feed of " + url)
            fg.link(href=url)
            fg.description("Filtered torrent feed of " + url)

            c = self.conn.cursor()
            for row in c.execute("SELECT * FROM rss WHERE rss_src=?", (url, )):
                #row = (date, title, link, description, size, category, categoryid, infoHash, rss_src)
                fe = fg.add_entry()
                fe.torrent.infohash(row[7])
                fe.torrent.contentlength(row[4])
                fe.id(row[2])
                fe.title(row[1])
                fe.link(href="magnet:?xt=urn:btih:"+row[7])
                fe.description(row[3] +
                               '<br/><a href="magnet:?xt=urn:btih:' + row[7] +
                               '">magnet:?xt=urn:btih:' + row[7] + "</a>")
                date = pytz.utc.localize(datetime.datetime.utcfromtimestamp(row[0]))
                fe.pubDate(date)

            fg.rss_str(pretty=True)
            fg.rss_file(self.subscribed[url]["saveas"])

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

def start_http(port):
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print("serving at port", port)
        httpd.serve_forever()

def main(args):
    rss = rss_store(args)
    rss.regisiter("https://nyaa.si/?page=rss", "static/nyaa.xml")
    rss.regisiter("https://sukebei.nyaa.si/?page=rss", "static/sukebei.xml")
    rss.regisiter("https://manga314.com/feed", "static/manga314.xml")
    rss.regisiter("https://cmczip.com/feed/", "static/cmczip.xml", {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:68.0) Gecko/20100101 Firefox/68.0",
        "Cookie": "cf_clearance=2a00bc1e9e2353c0cbbdf1022d6f2104026fd219-1612730326-0-150; __cfduid=dee56649dd56d8a1aa7cee406f3ee0ed51612404753"
    })


    thr = threading.Thread(target=start_http, args=(args.port, ))
    thr.start()

    while True:
        rss.update()
        print("synced on",
              datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
              "with", rss.size_db(), "entries")
        time.sleep(rss.loop_duration)

    thr.join()

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-name", type=str, default="rss.db", help="sqlite3 database file name")
    parser.add_argument("--gc-duration", type=int, default=4, help="garbage collection on old entries (days)")
    parser.add_argument("--loop-duration", type=int, default=(5 * 60), help="duration of refresh databases (seconds)")
    parser.add_argument("--port", type=int, default=8000, help="listen port")
    return parser

if __name__ == "__main__":
    parser = get_parser()
    main(parser.parse_args())
