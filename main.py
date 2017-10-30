# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import tweepy # twitter api wrapper
import imgurpython # imgur api wrapper
from imgurpython.helpers.error import ImgurClientError # imgurpython errors
from gfycat.client import GfycatClient # gfycat api wrapper
from gfycat.error import GfycatClientError # gfycat api errors
import login # our custom login object for all the api's we need
import paths # links to custom paths (e.g. for the log files)
import re
import time
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
try:
	t = login.twitter() # login and get the twitter object
except tweepy.TweepError as e:
	logger.critical('EXITING! Couldn\'t log in to Twitter: %s',str(e))
	raise SystemExit('Quitting - could not log in to Twitter!') # if we can't deal with Twitter, just stop altogether, and let it try again next time

# login to imgur
try:
	i = login.imgur() # login and get the imgur object
except ImgurClientError as e:
	logger.critical('EXITING! Couldn\'t log in to Imgur: %s',str(e))
	raise SystemExit('Quitting - could not log in to Imgur!') # if we can't deal with Imgur, just stop altogether, and let it try again next time






def main() :
	# find any submissions in this subreddit that are links to twitter.com
	# and reply to them
	try:
		subreddit = r.get_subreddit(subName,fetch=True) # fetch=True is necessary to test if we've really got a real subreddit
	except praw.errors.PRAWException as e:
		logger.critical('EXITING! Could not get subreddit %s',e.message)
		raise SystemExit('Quitting - could not get subreddit') # if we can't deal with reddit, just stop altogether, and let it try again next time
	else:
		for s in subreddit.get_new(limit=50) : # check the newest 50 submissions
			logger.debug('----------------------------------')
			logger.debug('SUBMISSION TITLE: %s',s.title)
			if s.domain in domains and not alreadyDone(s) :
				addComment(s)

# return True if we've already replied to this submission
def alreadyDone(s) :
	try:
		s.replace_more_comments(limit=None, threshold=0) # get unlimited list of top comments
	except AttributeError as e:
		logger.error("ERROR: could not find comments in post (thread possibly too old?) - %s", str(e)) # found this bug when testing on very old threads
		return True # skip this post and move on to the next one

	for comment in s.comments : # loop through all the top-level comments
		# if we wrote this top-level comment
		try:
			if comment.author.name == botName :
				return True
		except AttributeError as e:
			# a comment will have no author if it has been deleted, which will raise an attribute error
			pass
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
			logger.error("%s - Could not post tweet due to exception when finding/rehosting media - message:%s",s.id,str(e), exc_info=True)
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
			tweetText = re.sub(r"\bhttps?:\/\/t.co\/\w+\b",resolveLink(tweet), tweet.full_text, 0) # replace any t.co links in the tweet text with the resolved link; not only does this allow people to use them even if twitter is blocked, t.co links also probably cause reddit comments to be blocked as spam
			comment += re.sub(r"^","> ",redditEscape(tweetText), 0, re.MULTILINE) + "\n\n" # escape reddit formatting and add "> " quote syntax to the beginning of each line

			logger.debug('text after link replacement: ' + tweetText)
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
			comment += "^^I ^^am ^^a ^^bot ^^powered ^^exclusively ^^by ^^okra ^^and ^^Fred ^^Smoot ^^sayings"
			comment += " ^^| [^^[message ^^me]](https://www.reddit.com/message/compose?to=FleetFlotTheTweetBot)"
			comment += " ^^| [^^[source ^^code]](https://github.com/JohnMTorgerson/FleetFlotTheTweetBot)"
			comment += " ^^| ^^Skål!"

			try:
				s.add_comment(comment) # post comment to reddit
			except praw.errors.PRAWException as e:
				logger.error('%s - Could not comment: %s',s.id,e.message)
			except AttributeError as e:
				logger.error('%s - Could not comment. I have no idea why: %s',s.id,str(e), exc_info=True)
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
			e.custom = 'Could not find tweet for this id: ' + id + ' - error: ' + str(e)
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
	r = requests.get('https://api.streamable.com/import?url=' + url,auth=requests.auth.HTTPBasicAuth(login.loginStreamable.username,login.loginStreamable.password))
	shortcode = r.json()['shortcode'] # get shortcode from streamable for uploaded video, which we'll then check on to see if it got uploaded

	# wait until status is '2' or give up after 13 tries
	urls = {} # we'll return this
	tries = 12
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

# when passed a t.co shortlink, find and return the resolved link from the tweet entities
# we use a closure so that we can pass the tweet object from the function call (which occurs inside re.sub as a replace function: see http://stackoverflow.com/questions/7868554/python-re-subs-replace-function-doesnt-accept-extra-arguments-how-to-avoid)
def resolveLink(tweet) :
	def replaceLink(matchObj) :
		resolvedLink = '*[error resolving url]*' # the return variable; initially set to an error message
		try :
			shortLink = matchObj.group() # the t.co link
		except Exception as e :
			# log an error, and then do nothing, so that resolvedLink will be returned as the initial error message it was set to
			logger.error('Problem with resolving link, regex found a match but replace function couldn\'t access it: %s - replacing link with an error message', str(e))

		else :

			if hasattr(tweet,'entities') and 'urls' in tweet.entities : # if we have any urls in the tweet
				for ent in tweet.entities['urls'] : # loop through all the urls looking for our match
					if shortLink == ent['url'] :
						# try to find the actual url from the tweet object
						try :
							expandedURL = ent['expanded_url'] # get expanded url
						except KeyError as e:
							# if no 'expanded_url' for some reason, we'll just set expandedURL = shortLink and try to resolve the link by following its redirects with an HTTP request
							expandedURL = shortLink

							logger.error('Could not resolve shortlink:%s, no expanded_url in tweet entities; trying to resolve it manually - %s', shortLink, str(e))

						# whether that worked or not, we still need to test it to see if it redirects elsewhere
						# and if so, use the redirected url (because a bit.ly url, for example, would still get us stuck in reddit's spam filter)
						try :
							# follow any redirects and store that url
							session = requests.Session()
							resp = session.head(expandedURL, allow_redirects=True) # follow any redirects
							expandedURL = resp.url # save the redirected url
						except requests.exceptions.RequestException as e :
							# there was a problem trying to find the url to see if it redirected anywhere, so log the error
							# in the future, we may want to apply more sophisticated error handling here, with timeouts and so forth
							# in the meantime, we'll just do nothing, which will result in expandedURL
							# having either the value of the expanded url from the tweet object (ideally) or (worst case) the original t.co link if the expanded_url couldn't be found in the tweet object
							logger.error('HTTP request failed when trying to see if %s redirects anywhere, so we\'ll just post the original link; error: %s',expandedURL,str(e))

						# regardless of whether everything got resolved appropriately, we set resolvedLink to expandedURL, with some formatting
						# depending on which of the previous try blocks failed, expandedURL could at this point be
						# anything from the original t.co link to an intermediate shortlink (e.g. bit.ly) to the fully resolved url
						try :


							# format the link in reddit markup using the display_url
							resolvedLink = '[' + ent['display_url'] + '](' + expandedURL + ')'
						except KeyError as e :
							# if for some reason there's no display_url, just use the raw link
							resolvedLink = expandedURL
							logger.error('Could not find display_url when replacing link, so just posting raw link without formatting - error: %s', str(e))
						break
				else : # no break means we didn't find the url in entities
					# this is expected to happen with all t.co links to the tweet itself that the twitter API appends to the end of the tweet text
					# so we'll log it, and replace resolvedLink with an empty string, because we don't want to display those links
					resolvedLink = ''
					logger.debug('Could not find shortlink:%s in the tweet entities[\'urls\']; this is probably a link to the tweet itself, so replacing it with an empty string', shortLink)
			else :
				logger.error('Trying to replace shortlink:%s but tweet entities[\'urls\'] did not exist; replacing it with an error message', shortLink)
		return resolvedLink
	return replaceLink

if __name__ == "__main__":
    main()
