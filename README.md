# FleetFlotTheTweetBot

A simple Twitter bot for /r/minnesotavikings

## Functionality:

* Finds posts to /r/minnesotavikings that are twitter links
* Posts the text of the tweet
* Rehosts pics and gifs linked in the tweets to imgur and gfycat, respectively

## Planned enhancements:

* Rehost video links in tweets
* Supply direct links to articles that are linked to as shortened t.co urls in tweets
* Reply to and rehost twitter media linked directly in a post rather than as part of a whole tweet (i.e. twimg.com posts)
* Possibly reply to twitter links in comments?

Written in Python 3 using praw, tweepy, imgurpython, and gfycat