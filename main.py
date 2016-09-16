# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import tweepy # twitter api wrapper
import login # our custom login object for all the api's we need
import re
import time
from pprint import pprint
import warnings
warnings.simplefilter("ignore", ResourceWarning) # ignore resource warnings

# set some variables
botName = 'FleetFlotTheTweetBot' # our reddit username
subName = 'FleetFlotTheTweetBot' # the subreddit we're operating on

# login and get the subreddit object
r = login.reddit() # login to our account
subreddit = r.get_subreddit(subName)

# login and get the twitter object
t = login.twitter()

# find any submissions in this subreddit that are links to twitter.com
# and reply to them
def replyToTwitterPosts() :
	for s in subreddit.get_new(limit=50) :
		pprint('-----------------------------------')
		pprint('SUBMISSION TITLE: ' + s.title)
		if s.domain == 'twitter.com' and not alreadyDone(s) :
			addComment(s)

# return True if we've already replied to this submission
def alreadyDone(s) :
	s.replace_more_comments(limit=None, threshold=0)
	for comment in s.comments :
		# if we wrote this top-level comment
		if comment.author.name == botName :
			return True
	return False

# reply to the submission with the contents of the tweet
def addComment(s) :
	tweet = getTweet(s.url, s.title) # return tweet object
	pprint('replying to ' + s.title)
	s.add_comment(redditEscape(tweet.text))

# get the contents of the tweet
def getTweet(url, title) :
	# first find the tweet id from the url
	pprint(url)
	regex = re.compile(r"(?<=\/)(\d+)$") # regex pattern to find the tweet id from the url
	id = re.search(regex,url).group(1)
	
	# now get the actual tweet and return it
	tweet = t.get_status(id)
	return tweet
	
# escape any reddit markdown from the string
# (right now all this does is escape '#' from the beginning of a line)
def redditEscape(string) :
	regex = re.compile(r"(^|\n\n)#") # find '#' at beginning of string or double newline
	string = re.sub(regex,"\#",string) # add a '\' before any matches
	return string
	
		
replyToTwitterPosts()