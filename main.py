# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import tweepy # twitter api wrapper
import imgurpython # imgur api wrapper
import gfycat # gfycat api wrapper
import login # our custom login object for all the api's we need
import re # regex
import time # time
import json # to display data for debugging
from pprint import pprint
import warnings
warnings.simplefilter("ignore", ResourceWarning) # ignore resource warnings

# set some variables
botName = 'FleetFlotTheTweetBot' # our reddit username
subName = 'FleetFlotTheTweetBot' # the subreddit we're operating on

# login and get the subreddit object
try:
	r = login.reddit() # login to our account
except:
	raise SystemExit('Error: could not log in to Reddit!') # for now, if we can't deal with reddit, just stop altogether, and let it try again next time
else:
	subreddit = r.get_subreddit(subName)

# login and get the twitter object
t = login.twitter()

# login and get the imgur object
i = login.imgur()

# find any submissions in this subreddit that are links to twitter.com
# and reply to them
def replyToTwitterPosts() :
	try:
		for s in subreddit.get_new(limit=50) :
			pprint('-----------------------------------')
			pprint('SUBMISSION TITLE: ' + s.title)
			if s.domain == 'twitter.com':# and not alreadyDone(s) :
				addComment(s)
	except praw.errors.InvalidSubreddit:
		raise SystemExit('Error: invalid subreddit!') # for now, if we can't deal with reddit, just stop altogether, and let it try again next time

# return True if we've already replied to this submission
def alreadyDone(s) :
	s.replace_more_comments(limit=None, threshold=0)
	for comment in s.comments : # loop through all the top-level comments
		# if we wrote this top-level comment
		if comment.author.name == botName :
			return True
	return False

# reply to the submission with the contents of the tweet
def addComment(s) :
	tweet = getTweet(s.url, s.title) # return tweet object
	if tweet != None : # if we were able to find a tweet
		tweetMedia = getTweetMedia(tweet) # find any media in the tweet and return as list
		
		# the following commented code is just for testing, to view the whole json object of a tweet:
#		print('\n\n\n')
#		json.dumps(tweet)
#		print('\n\n\n')
#		exit()

		pprint('title:' + s.title)
		
		# --- FORMAT COMMENT --- #
		lineSep = "--------------------"
		# Text
		comment = redditEscape(tweet.text) + "\n\n" + lineSep + "\n\n"
		# Media
		if len(tweetMedia) > 0 : # if there's any media, display links
			comment += "Media:\n\n"
			for url in tweetMedia :
				comment += url + "\n\n"
			comment += lineSep + "\n\n"
		# Disclaimer
		comment += "^^I ^^am ^^a ^^bot"
		
		# comment out the actual posting functionality during testing:
		# post comment
#		pprint(comment)
#		s.add_comment(comment)
	else : # we couldn't find a tweet
		# log error here
		pprint('Couldn\'t find tweet id!')
	

# get the contents of the tweet
# if we can't find the tweet, return None
def getTweet(url, title) :
	# first find the tweet id from the url
	pprint(url)
	regex = re.compile(r"(?<=\/status\/)(\d+)") # regex pattern to find the tweet id from the url
	matches = re.search(regex,url)
	if hasattr(matches, 'group') : # if we have a regex match
		id = matches.group(1) # extract the id
		try:
			tweet = t.get_status(id) # get the actual tweet
		except:
			raise SystemExit('Error: could not get tweet!') # for now, if we can't deal with twitter, just stop altogether, and let it try again next time
		else:
			return tweet # return it
	else :
		return None # we couldn't find the tweet from the url
	
# find any media in the tweet that we care about (e.g. pics, videos)
# rehost it if possible, and return all of it as a list
def getTweetMedia(tweet) :
	tweetMedia = [] # list in which we'll store the media

	# find any media and add to tweetMedia
	if hasattr(tweet,'extended_entities') and 'media' in tweet.extended_entities : # if we have any media at all?
		for ent in tweet.extended_entities['media'] : # loop through all the media and add them to tweetMedia
			
			# GIF or VIDEO
			if 'video_info' in ent : # if the media is a gif or a video
				variants = ent['video_info']['variants'] # array of different variants (file types/resolutions/etc)
				
				# GIF
				if ent['type'] == 'animated_gif' : # it's a gif (but is probably actually a silent mp4)
					for variant in variants :
						if variant['content_type'] == 'video/mp4' :
							url = variant['url']
							pprint('GIF - url:' + url)
							# eventually, we'll want to rehost the gif and then append it to tweetMedia
							# in the mean time, we will not append the original url
							# tweetMedia.append(url)
							break
					else : # if we didn't find anything
						pprint("GIF, didn't recognize content_type")
						
				# VIDEO
				elif ent['type'] == 'video' :
					for variant in variants :
						if variant['content_type'] == 'video/mp4' :
							url = variant['url']
							pprint('VIDEO - url:' + url)
							# eventually, we'll want to rehost the video and then append it to tweetMedia
							# in the mean time, we will not append the original url
							# tweetMedia.append(url)
							break
					else : # if we didn't find anything
						pprint("VIDEO, didn't recognize content_type")
						
			# IMAGE
			elif 'media_url_https' in ent : # if not, the media is a static image
				url = ent['media_url_https']
				pprint('PICTURE - media_url_https:' + url)
				# rehost static image on imgur
				try:
					imgurURL = getImgurURL(url)
				except ImgurClientError as e:
					# before production, log this message instead of printing it:
					pprint("ERROR! Could not upload static image to imgur: " + e.error_message + ' ' + e.status_code)
				else:
					# if successful, append the imgur URL to the tweetMedia list
					tweetMedia.append(imgurURL)
					pprint('successfully uploaded to imgur: ' + imgurURL)
				
			else : # if we're here, there's no media at all
				pprint('extended_entities, but no video_info or media_url_https???')
				
	else : # we didn't find any media
		pprint('no extended_entities at all!!!')
		
	return tweetMedia
	
# given a url to a (static) image, upload to imgur and return the imgur url
def getImgurURL(url) :
	ext = re.search("\.([a-zA-Z0-9]{3,4})$",url).group(1) # find the file extension
	upload = i.upload_from_url(url, config=None, anon=True)
	imgurURL = "http://imgur.com/" + upload['id'] + "." + ext
	return imgurURL
	
# escape any reddit markdown from the string
# (right now all this does is escape '#' from the beginning of a line)
def redditEscape(string) :
	regex = re.compile(r"(^|\n\n)#") # find '#' at beginning of string or double newline
	string = re.sub(regex,"\#",string) # add a '\' before any matches
	return string
	
		
replyToTwitterPosts()