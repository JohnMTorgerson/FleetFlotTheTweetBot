# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import tweepy # twitter api wrapper
import imgurpython # imgur api wrapper
from imgurpython.helpers.error import ImgurClientError # imgurpython errors
from gfycat.client import GfycatClient # gfycat api wrapper
from gfycat.error import GfycatClientError # gfycat api errors
import login # our custom login object for all the api's we need
import paths # links to custom paths (e.g. for the log files)
import re # regex
import time # time
import requests
import json # to display data for debugging
from pprint import pprint
import warnings
import logging
import logging.handlers

# set some global variables
botName = 'FleetFlotTheTweetBot' # our reddit username
subName = 'minnesotavikings' # the subreddit we're operating on
domains = ['twitter.com','mobile.twitter.com'] # twitter domains to check submissions against

# turn off some warnings
warnings.simplefilter("ignore", ResourceWarning) # ignore resource warnings

# configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# timed rotating handler to log to file at INFO level, rotate every 1 days
main_handler = logging.handlers.TimedRotatingFileHandler(paths.logs + 'main_log.log',when="d",interval=1)
main_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
main_handler.setFormatter(formatter)
logger.addHandler(main_handler)
# handler to log to a different file at ERROR level
error_handler = logging.FileHandler(paths.logs + 'error_log.log')
error_handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

# login to reddit
try: 
	r = login.reddit() # login to our account
except praw.errors.PRAWException as e:
	logger.critical('EXITING! Couldn\'t log in to reddit: %s %s',e.message,e.url)
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
		logger.critical('EXITING! Invalid subreddit? %s',e.message)
		raise SystemExit('Quitting - invalid subreddit??') # if we can't deal with reddit, just stop altogether, and let it try again next time
	else:
		for s in subreddit.get_new(limit=50) : # check the newest 50 submissions
			logger.debug('----------------------------------')
			logger.debug('SUBMISSION TITLE: %s',s.title)
			if s.domain in domains and not alreadyDone(s) :
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
		tweet = getTweet(s.url) # return tweet object
	except AttributeError as e: # we couldn't find the tweet id from the url
		logger.error("%s - %s",s.id,e.custom) # print custom error message
	except tweepy.error.TweepError as e: # we couldn't find the tweet from the id
		logger.error("%s - %s",s.id,e.custom) # print custom error message
	else:
		try:
			tweetMedia = getTweetMedia(tweet) # find any media in the tweet and return as list
		except Exception as e:
			logger.error("%s - Could not post tweet due to exception when finding/rehosting media - message:%s",s.id,str(e))
			if hasattr(e,'custom'):
				logger.error("%s - %s",s.id,e.custom) # print custom error message
		else:
			logger.debug('title: %s',s.title)
			logger.debug('text: %s',tweet.full_text)
			
			# --- FORMAT COMMENT --- #
			lineSep = "--------------------"
			
			# Tweet author
			comment = "**[@" + tweet.user.screen_name + "](https://www.twitter.com/" + tweet.user.screen_name + ")** (" + tweet.user.name + "):\n\n" 
			
			# Text
			comment += re.sub(r"^","> ",redditEscape(tweet.full_text), 0, re.MULTILINE) + "\n\n" # escape reddit formatting and add "> " quote syntax to the beginning of each line
			
			# Media
			if len(tweetMedia) > 0 : # if there's any media, display links
				comment += "Rehosted Media:\n\n"
				for media in tweetMedia :
					string = ""
					if isinstance(media,dict) : # if the media was a video, it will be a dict with possibly multiple links of different bitrates
						for key in media :
							string += "[[" + key + "]](" + media[key] + ") "
						if string == "" : # i.e. if the dict was empty
							string = "error rehosting video. Sorry!" # we should never get here, because an exception should have been raised earlier
						string = "Video: " + string
					else : # otherwise, we assume it's a string, a single url
						string = media
					comment += "* " + string + "\n\n"
					
			# Footer
			comment += lineSep + "\n\n"
			comment += "^^I ^^am ^^a ^^bot ^^made ^^of ^^recycled ^^Adrian ^^Peterson ^^knees"
			comment += " ^^| [^^[message ^^me]](https://www.reddit.com/message/compose?to=FleetFlotTheTweetBot)"
			comment += " ^^| [^^[source ^^code]](https://github.com/JohnMTorgerson/FleetFlotTheTweetBot)"
			comment += " ^^| ^^Skål!"
			
			try:
				s.add_comment(comment) # post comment to reddit
			except praw.errors.PRAWException as e:
				logger.error('%s - Could not comment: %s',s.id,e.message)
			else:
				logger.info("Successfully added comment on %s!",s.id)

# get the contents of the tweet
# if we can't find the tweet, raise an exception
def getTweet(url) :
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
			tweet = t.get_status(id, tweet_mode='extended') # get the actual tweet
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
					bitrate = 0
					url = ''
					for variant in variants : # loop through all the possible versions of the video
						if variant['content_type'] == 'video/mp4' and variant['bitrate'] > bitrate : # save this version if it's the highest res we've seen so far
							bitrate = variant['bitrate']
							url = variant['url']
							logger.debug('video variants - bitrate=' + str(bitrate) + ' url=' + url)
					if url != '' : # we found a video	
						logger.debug('VIDEO - url:' + url)
						
						# rehost the video on Streamable and append urls to tweetMedia
						try:
							vids = getStreamableURLs(url)
						except requests.exceptions.RequestException as e:
							e.custom = 'Could not upload to Streamable. RequestException: ' + str(e)
							raise
						else:
							tweetMedia.append(vids)

					else : # we didn't find anything
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
		
# given a url to a twitter video, upload to streamable and return a dict with streamable urls to the video (2 videos, for desktop and mobile)
def getStreamableURLs(url) :
	params = {'url': url}
	r = requests.get('https://api.streamable.com/import', params=params) # initiate upload
		
	shortcode = r.json()['shortcode']
	
	# wait until status is '2' or give up after 10 tries
	urls = {} # we'll return this
	tries = 10
	while tries >=0 :
		response = requests.get('https://api.streamable.com/videos/' + shortcode)
		response.json()
		status = response.json()['status']
		files = response.json()['files']
		if status == 2 : # success, but we still have to check to see if we have any url's yet
			if 'mp4' in files and files['mp4'].get('url','') != '' : # we have a desktop url
				urls['desktop'] = 'https:' + files['mp4']['url']
			if 'mp4-mobile' in files and files['mp4-mobile'].get('url','') != '' : # we have a mobile url
				urls['mobile'] = 'https:' + files['mp4-mobile']['url']
				
			# if we have both a desktop and a mobile url, break out of the loop
			# (if we have neither or just 1 of the 2, we'll keep trying)
			if 'desktop' in urls and 'mobile' in urls :
				break
		elif status == 3 : # error
			raise requests.exceptions.RequestException("Could not upload, returned status==3!")
			break
		time.sleep(5) # sleep for 5 seconds and then try again
		tries -= 1 # decrement tries
	else : # no-break: we timed out without getting a successful response
		raise requests.exceptions.RequestException("Could not retrieve any URLs in time, so we gave up!")
		
	# if we're here, we've gotten at least a desktop or a mobile url, or both
	return urls

# escape any reddit markdown from the string
def redditEscape(string) :
	# escape leading hashtags ('#')
	string = re.sub(r"^#","\#",string,0,re.MULTILINE)
	
	# delete leading spaces/tabs (so as not to trigger reddit's 'code' formatting)
	string = re.sub(r"^[ \t]+","",string,0,re.MULTILINE)

	# double space, because reddit needs two newlines to actually display a line break
	# (the regex actually only adds a newline at the end of a line if there's another line after it with characters in it)
	string = re.sub(r"(?<=.(?=\n.))","\n",string,0,re.MULTILINE)

	return string
	
if __name__ == "__main__":
    main()