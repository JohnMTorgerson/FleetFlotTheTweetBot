# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import tweepy # twitter api wrapper
import imgurpython # imgur api wrapper
from imgurpython.helpers.error import ImgurClientError # imgurpython errors
from gfycat.client import GfycatClient # gfycat api wrapper
from gfycat.error import GfycatClientError # gfycat api errors
import login # our custom login object for all the api's we need
import re # regex
import time # time
import json # to display data for debugging
from pprint import pprint
import warnings
import logging

# set some global variables
botName = 'FleetFlotTheTweetBot' # our reddit username
subName = 'FleetFlotTheTweetBot' # the subreddit we're operating on

# turn off some warnings
warnings.simplefilter("ignore", ResourceWarning) # ignore resource warnings

# configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler('fleetflot.log')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# login to reddit
try: 
	r = login.reddit() # login to our account
except praw.errors.PRAWException as e:
	logger.error('EXITING! Couldn\'t log in to reddit: %s %s',e.message,e.url)
	raise SystemExit('Quitting - could not log in to Reddit!') # if we can't deal with reddit, just stop altogether, and let it try again next time

# login to twitter
t = login.twitter() # login and get the twitter object

# login to imgur
i = login.imgur() # login and get the imgur object






def main() :
	# find any submissions in this subreddit that are links to twitter.com
	# and reply to them
	try:
		subreddit = r.get_subreddit(subName,fetch=True) # fetch=True is necessary to test if we've really got a real subreddit
	except praw.errors.PRAWException as e:
		logger.error('EXITING! Invalid subreddit? %s',e.message)
		raise SystemExit('Quitting - invalid subreddit??') # if we can't deal with reddit, just stop altogether, and let it try again next time
	else:
		for s in subreddit.get_new(limit=5) :
			logger.debug('----------------------------------')
			logger.debug('SUBMISSION TITLE: %s',s.title)
			if s.domain == 'twitter.com':# and not alreadyDone(s) :
				addComment(s)

# return True if we've already replied to this submission
def alreadyDone(s) :
	s.replace_more_comments(limit=None, threshold=0) # get unlimited list of top comments
	for comment in s.comments : # loop through all the top-level comments
		# if we wrote this top-level comment
		if comment.author.name == botName :
			return True
	return False

# reply to the submission with the contents of the tweet
def addComment(s) :
	logger.info("######## Found new tweet ######## REDDIT:%s TWITTER:%s", s.id, s.url ) # log the submission id and twitter URL

	try:
		tweet = getTweet(s.url, s.title) # return tweet object
	except AttributeError as e: # we couldn't find the tweet id from the url
		logger.error("%s - post id:%s",e.custom,s.id) # print custom error message
	except tweepy.error.TweepError as e: # we couldn't find the tweet from the id
		logger.error("%s - post id:%s",e.custom,s.id) # print custom error message
	else:
		try:
			tweetMedia = getTweetMedia(tweet) # find any media in the tweet and return as list
		except Exception as e:
			logger.error("Could not post tweet due to exception when finding/rehosting media - post id:%s - message:%s",s.id,str(e))
			if hasattr(e,'custom'):
				logger.error("%s - post id:%s",e.custom,s.id) # print custom error message
		else:
			# the following commented code is just for testing, to view the whole json object of a tweet:
			#print('\n\n\n')
			#json.dumps(tweet)
			#print('\n\n\n')
			#exit()

			logger.debug('title: %s',s.title)
			
			# --- FORMAT COMMENT --- #
			lineSep = "--------------------"
			
			# Tweet author
			# PUT TWEET AUTHOR HERE
			comment = "**[@" + tweet.user.screen_name + "](https://www.twitter.com/" + tweet.user.screen_name + ")** (" + tweet.user.name + "):\n\n" 
			
			# Text
			comment += "> " + redditEscape(tweet.text) + "\n\n"
			
			# Media
			if len(tweetMedia) > 0 : # if there's any media, display links
				comment += "Rehosted Media:\n\n"
				for url in tweetMedia :
					comment += "* " + url + "\n\n"
					
			# Footer
			comment += lineSep + "\n\n"
			comment += "^^I ^^am ^^a ^^bot ^^made ^^of ^^recycled ^^Adrian ^^Peterson ^^knees"
			comment += " ^^| [^^[message ^^me]](https://www.reddit.com/message/compose?to=FleetFlotTheTweetBot)"
			comment += " ^^| [^^[source ^^code]](https://github.com/JohnMTorgerson/FleetFlotTheTweetBot)"
			comment += " ^^| ^^Skål!!"
			
			try:
				pass
				#s.add_comment(comment) # post comment to reddit
			except praw.errors.PRAWException as e:
				logger.error('Could not comment on %s: %s',s.id,e.message)
			else:
				logger.info("Successfully added comment on %s!",s.id)

# get the contents of the tweet
# if we can't find the tweet, raise an exception
def getTweet(url, title) :
	logger.debug(url)

	# first find the tweet id from the url
	regex = re.compile(r"(?<=\/status\/)(\d+)") # regex pattern to find the tweet id from the url
	matches = re.search(regex,url)
	try:
		id = matches.group(1) # extract the id
	except AttributeError as e: # no regex match for the id, so raise an exception
		e.custom = 'Could not find tweet id from url:' + url
		raise
	else: # we found the tweet id
		try:
			tweet = t.get_status(id) # get the actual tweet
		except tweepy.error.TweepError as e: # we couldn't find the tweet from the id
			e.custom = 'Could not find tweet for this id: ' + id + ' - Tweepy error code: ' + str(e.api_code)
			raise
		else:
			return tweet # return it
	
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
							logger.debug('GIF - url:' + url)
							
							# rehost the gif on gfycat and add the new url
							try:
								gfy = GfycatClient()
								response = gfy.upload_from_url(url)
								rehostURL = "http://www.gfycat.com/" + response['gfyname']
							except GfycatClientError as e:
								# set custom error message and raise exception
								e.custom = 'Could not upload to gfycat. GfyCatClientError: ' + str(e)
								raise
							except KeyError as e: # KeyError will be raised if we could connect to gfycat, but couldn't upload (e.g. the url we tried to upload was bad)
								# set custom error message and raise exception
								e.custom = 'Could not upload to gfycat. Probably a bad upload url. KeyError: ' + str(e) + ' doesn\'t exist in response. JSON response was: ' + str(response)
								raise
							else:
								tweetMedia.append(rehostURL)
							break
					else : # no-break: we didn't find anything
						logger.error("GIF, didn't recognize content_type: %s",ent['url'])
						
				# VIDEO
				elif ent['type'] == 'video' :
					for variant in variants :
						if variant['content_type'] == 'video/mp4' :
							url = variant['url']
							logger.debug('VIDEO - url:' + url)
							# eventually, we'll want to rehost the video and then append it to tweetMedia
							# in the mean time, we will just append an error message to display in our post
							tweetMedia.append("This tweet contained a video, but I can't rehost those yet ◔̯◔ sorry!")
							logger.warning("Cannot rehost video links yet: %s",url)
							break
					else : # no-break: we didn't find anything
						logger.error("VIDEO found, but didn't recognize content_type: %s",ent['url'])
						
			# IMAGE
			elif 'media_url_https' in ent : # if not, the media is a static image
				url = ent['media_url_https']
				logger.debug('PICTURE - media_url_https: %s',url)
				# rehost static image on imgur
				try:
					imgurURL = getImgurURL(url)
				except ImgurClientError as e:
					# set custom error message and raise exception
					e.custom = "Could not upload static image to imgur: " + str(e)
					raise
				else:
					# if successful, append the imgur URL to the tweetMedia list
					tweetMedia.append(imgurURL)
					logger.debug('Successfully uploaded to imgur: %s',imgurURL)
				
			else : # if we're here, there's no media at all
				logger.error('Thought we found media, but couldn\'t find urls (extended_entities exists, but no video_info or media_url_https???)')
				
	else : # we didn't find any media
		logger.debug('no extended_entities at all!!!')
		
	return tweetMedia
	
# given a url to a (static) image, upload to imgur and return the imgur url
def getImgurURL(url) :
	try:
		ext = re.search("\.([a-zA-Z0-9]{3,4})$",url).group(1) # find the file extension
	except AttributeError as e:
		e.custom = "Could not find file extension from URL when trying to upload to imgur"
		raise
	else:
		upload = i.upload_from_url(url, config=None, anon=True)
		imgurURL = "http://imgur.com/" + upload['id'] + "." + ext
		return imgurURL
	
# escape any reddit markdown from the string
# (right now all this does is escape '#' from the beginning of a line)
def redditEscape(string) :
	regex = re.compile(r"(^|\n\n)#") # find '#' at beginning of string or double newline
	string = re.sub(regex,"\#",string) # add a '\' before any matches
	return string
	
if __name__ == "__main__":
    main()