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
import requests.adapters

SCRIPT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_FILE_PATH)

class timeout(requests.adapters.TimeoutSauce):
    def __init__(self, *args, **kwargs):
        if kwargs["connect"] is None:
            kwargs["connect"] = 30
        if kwargs["read"] is None:
            kwargs["read"] = 30
        super(timeout, self).__init__(*args, **kwargs)

requests.adapters.TimeoutSauce = timeout

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
                                                     author TEXT,
                                                     rss_src TEXT,
                                                     rss_type TEXT,
                                                     size TEXT,
                                                     category TEXT,
                                                     categoryid TEXT,
                                                     infoHash TEXT PRIMARY KEY)''')
        self.conn.commit()

    def regisiter(self, url, saveas, httpheader, rss_type):
        self.subscribed[url] = {
            "lastupdate": self.max_update_time(url),
            "saveas": saveas,
            "httpheader": httpheader,
            "rss_type": rss_type
        }

    def write_db(self, rss_list, rss_src, rss_type):
        c = self.conn.cursor()

        if rss_type == "nyaa":
            tuples = [(time.mktime(x["published_parsed"]),
                       x.get("title"),
                       x.get("id"),
                       x.get("summary"),
                       x.get("author"),
                       rss_src,
                       rss_type,
                       x.get("nyaa_size"),
                       x.get("nyaa_category"),
                       x.get("nyaa_categoryid"),
                       x.get("nyaa_infohash")) for x in rss_list]
        else:
            tuples = [(time.mktime(x["published_parsed"]),
                       x.get("title"),
                       x.get("link"),
                       x.get("description"),
                       x.get("author"),
                       rss_src,
                       rss_type,
                       "", "", "",
                       hashlib.sha256((x["title"] + x["published"]).encode("utf-8")).hexdigest())
                      for x in rss_list]

        c.executemany('''INSERT OR REPLACE INTO
                           rss(date, title, link, description, author, rss_src, rss_type, size, category, categoryid, infoHash)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)
                      ''', tuples)
        self.conn.commit()

    def view(self):
        c = self.conn.cursor()
        for row in c.execute("SELECT * FROM rss"):
            print(row[1], row[8])
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

    def filter(self, entries, rss_type):
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
                    if rss_type == "nyaa":
                        if re.match(key["category"], entry.get("nyaa_category")) and (re.match(key["regex"], entry.title)):
                            filtered.append(entry)
                            break
                    else:
                        if (key["category"] == ".*" and
                            (re.match(key["regex"], entry.title) or re.match(key["regex"], entry.author))):
                            filtered.append(entry)
                            break;

        return filtered

    def delete_old_db_entries(self, limit, rss_src):
        c = self.conn.cursor()
        c.execute("DELETE FROM rss WHERE date<? AND rss_src=?", (limit, rss_src))
        self.conn.commit()

    def gen_torrent_feed(self, url):
        fg = feedgen.feed.FeedGenerator()
        fg.load_extension("torrent", atom=True, rss=True)

        fg.id(url)
        fg.title("Filtered torrent feed of " + url)
        fg.link(href=url)
        fg.description("Filtered torrent feed of " + url)

        c = self.conn.cursor()
        for row in c.execute("SELECT date, title, link, description, author, size, category, categoryid, infoHash FROM rss WHERE rss_src=?", (url, )):
            fe = fg.add_entry()
            fe.torrent.infohash(row[8])
            fe.torrent.contentlength(row[5])
            fe.id(row[2])
            fe.title(row[1])
            fe.author({"name": row[4]})
            fe.link(href="magnet:?xt=urn:btih:"+row[8])
            fe.description(row[3] +
                           '<br/><a href="magnet:?xt=urn:btih:' + row[8] +
                           '">magnet:?xt=urn:btih:' + row[8] + "</a>")
            date = pytz.utc.localize(datetime.datetime.utcfromtimestamp(row[0]))
            fe.pubDate(date)

        fg.rss_str(pretty=True)
        fg.rss_file(self.subscribed[url]["saveas"])

    def gen_basic_feed(self, url):
        fg = feedgen.feed.FeedGenerator()

        fg.id(url)
        fg.title("Filtered torrent feed of " + url)
        fg.link(href=url)
        fg.description("Filtered torrent feed of " + url)

        c = self.conn.cursor()
        for row in c.execute("SELECT date, title, link, description, author FROM rss WHERE rss_src=?", (url, )):
            fe = fg.add_entry()
            fe.id(row[2])
            fe.title(row[1])
            fe.link(href=row[2])
            fe.description(row[3])
            fe.author({"name": row[4]})
            date = pytz.utc.localize(datetime.datetime.utcfromtimestamp(row[0]))
            fe.pubDate(date)

        fg.rss_str(pretty=True)
        fg.rss_file(self.subscribed[url]["saveas"])

    def update(self):
        for url in self.subscribed:
            try:
                resp = requests.get(url, timeout=30.0, headers=self.subscribed[url]["httpheader"])
            except requests.ReadTimeout:
                continue

            nyaa = feedparser.parse(io.BytesIO(resp.content))

            entries = [x for x in nyaa.entries if time.mktime(x.published_parsed) > self.subscribed[url]["lastupdate"]]
            self.subscribed[url]["lastupdate"] = max([time.mktime(x.published_parsed) for x in nyaa.entries] + [self.subscribed[url]["lastupdate"]])

            filtered = self.filter(entries, self.subscribed[url]["rss_type"])

            self.write_db(filtered, url, self.subscribed[url]["rss_type"])
            self.delete_old_db_entries(self.subscribed[url]["lastupdate"] - self.gc_duration, url)


            if self.subscribed[url]["rss_type"] == "nyaa":
                self.gen_torrent_feed(url)
            else:
                self.gen_basic_feed(url)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="static", **kwargs)

def start_http(port):
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print("serving at port", port)
        httpd.serve_forever()

def main(args):
    rss = rss_store(args)
    rss.regisiter(url="https://nyaa.si/?page=rss",
                  saveas="static/nyaa.xml",
                  httpheader={},
                  rss_type="nyaa")
    rss.regisiter(url="https://sukebei.nyaa.si/?page=rss",
                  saveas="static/sukebei.xml",
                  httpheader={},
                  rss_type="nyaa")
    rss.regisiter(url="http://dl-zip.com/feed/",
                  saveas="static/dl-zip.xml",
                  httpheader={},
                  rss_type="basic")
    rss.regisiter(url="https://bszip.com/feed",
                  saveas="static/bszip.xml",
                  httpheader={},
                  rss_type="basic")
    rss.regisiter(url="https://twitter2rss.nomadic.name/imys_staff?",
                  saveas="static/twitterimys.xml",
                  httpheader={},
                  rss_type="basic")

    if not args.no_server:
        thr = threading.Thread(target=start_http, args=(args.port, ))
        thr.start()

    while True:
        try:
            rss.update()
        except Exception as e:
            print(e)

        print("synced on",
              datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"),
              "with", rss.size_db(), "entries")
        time.sleep(rss.loop_duration)

    if not args.no_server:
        thr.join()

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-name", type=str, default="rss.db", help="sqlite3 database file name")
    parser.add_argument("--gc-duration", type=int, default=4, help="garbage collection on old entries (days)")
    parser.add_argument("--loop-duration", type=int, default=(5 * 60), help="duration of refresh databases (seconds)")
    parser.add_argument("--port", type=int, default=8000, help="listen port")
    parser.add_argument("--no-server", action="store_true", help="turn off the python http server. Only update rss")
    return parser

if __name__ == "__main__":
    parser = get_parser()
    main(parser.parse_args())
