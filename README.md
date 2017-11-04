# FleetFlotTheTweetBot

A simple Twitter bot for /r/minnesotavikings

## Functionality:

* Finds posts to /r/minnesotavikings that are twitter links
* Posts the text of the tweet
* Fully resolves any links in the tweet to their source (e.g. t.co -> bit.ly -> mnvkn.gs -> vikings.com)
* Rehosts pics, gifs, and videos linked in the tweets to imgur, gfycat, and streamable, respectively

## Planned enhancements:

* Reply to and rehost twitter media linked directly in a post rather than as part of a whole tweet (i.e. twimg.com posts)
* Possibly reply to twitter links in the text of a self post?
* Possibly reply to twitter links in comments?

Written in Python 3 using the following modules: PRAW (5.2.0), Tweepy, Imgurpython, and Gfycat
