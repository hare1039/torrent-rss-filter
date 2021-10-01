# torrent-rss-filter

A simple RSS filter: 
It reads from RSS sources, filter by wanted keyword & remove unwanted keyword, and save as new rss feed.

Currently you need to change the source directly in the code, but its fairly simple.

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
