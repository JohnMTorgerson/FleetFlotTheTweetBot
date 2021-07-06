# Reply to any submission in 'subName' that's a Twitter link

import praw # reddit api wrapper
import prawcore # some praw exceptions inherit from here
import tweepy # twitter api wrapper
import imgurpython # imgur api wrapper
from imgurpython.helpers.error import ImgurClientError # imgurpython errors
# from gfycat.client import GfycatClient # gfycat api wrapper
# from gfycat.error import GfycatClientError # gfycat api errors
from gfypy import Gfypy
from gfypy import GfypyException
import login # our custom login object for all the api's we need
import paths # links to custom paths (e.g. for the log files)
import re
import regex # one of the regex patterns we need to use requires a possessive quantifier, which the 're' library doesn't support. This library does.
import time
import multiprocessing # only using this to time-out the big url regex in case of catastrophic backtracking
import queue as queueError # for queue.empty exception
import requests
import json # to display data for debugging
from pprint import pprint
import warnings
import logging
import logging.handlers
import os
from dotenv import load_dotenv
load_dotenv()

# set some global variables
botName = 'FleetFlotTheTweetBot' # our reddit username
subName = os.environ['SUB_NAME'] # subreddit
num_threads = int(os.environ['NUM_THREADS']) # the number of recent threads to check

# turn off some warnings
warnings.simplefilter("ignore", ResourceWarning) # ignore resource warnings

# configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# timed rotating handler to log to file at DEBUG level, rotate every 100 KB
debug_handler = logging.handlers.RotatingFileHandler(paths.logs + 'debug_log.log', mode='a', maxBytes=100000, backupCount=50, encoding=None, delay=False)
debug_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
debug_handler.setFormatter(formatter)
logger.addHandler(debug_handler)

# timed rotating handler to log to file at INFO level, rotate every 100 KB
main_handler = logging.handlers.RotatingFileHandler(paths.logs + 'main_log.log', mode='a', maxBytes=100000, backupCount=50, encoding=None, delay=False)
main_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
main_handler.setFormatter(formatter)
logger.addHandler(main_handler)

# handler to log to a different file at ERROR level, rotate every 100 KB
error_handler = logging.handlers.RotatingFileHandler(paths.logs + 'error_log.log', mode='a', maxBytes=100000, backupCount=50, encoding=None, delay=False)
error_handler.setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

# separate handler to log the ID of each submission we comment on, rotate every 100 KB
comment_logger = logging.getLogger('comments')
comment_logger.setLevel(logging.INFO)
comment_handler = logging.handlers.RotatingFileHandler(paths.logs + 'comment_log.log', mode='a', maxBytes=100000, backupCount=50, encoding=None, delay=False)
comment_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
comment_handler.setFormatter(formatter)
comment_logger.addHandler(comment_handler)

# login to reddit
try:
	r = login.reddit() # login to our account
except praw.exceptions.PRAWException as e:
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

# login to gfycat
try:
	g = login.gfycat() # login and get the gfycat object
except Exception as e:
	logger.critical('EXITING! Couldn\'t log in to Gfycat: %s',str(e))
	raise SystemExit('Quitting - could not log in to Gfycat!') # if we can't deal with Gfycat, just stop altogether, and let it try again next time




def main() :
	# find any submissions in this subreddit that are links to twitter.com
	# and reply to them; then loop through all comments in that submission
	# and reply to any twitter links found therein
	try:
		subreddit = r.subreddit(subName)
		# loop through submissions
		for s in subreddit.new(limit=num_threads) : # check the newest num_threads submissions
			logger.debug('----------------------------------')
			logger.debug('SUBMISSION TITLE: %s',s.title)
			pattern = re.compile("^https?:\/\/(www\.|mobile\.)?twitter\.com")

			########-------- Reply to Submission --------########
			logger.debug('Checking submission itself for Twitter link...')
			# if the domain is twitter.com and we haven't already commented, proceed
			if pattern.match(s.url) is not None and not alreadyDone(s) :
				# create reply
				reply = composeReply(s.url,s.id)
				#reply = None

				# post comment as a top-level reply to the submission
				# (if there was a serious error in composeReply
				# it will just return None, and we won't reply)
				if reply is not None :
					try:
						s.reply(reply) # post comment to reddit
					except praw.exceptions.RedditAPIException as e:
						# for subexception in e.items:
						# 	print(subexception.error_type)
						logger.error('%s - Could not comment: %s',s.id,e.items)
					except praw.exceptions.PRAWException as e:
						logger.error('%s - Could not comment: %s',s.id,str(e))
					except AttributeError as e:
						logger.error('%s - Could not comment. I have no idea why: %s',s.id,str(e), exc_info=True)
					else:
						logger.info("Successfully added comment on %s!",s.id)
						comment_logger.info(s.id) # log the ID of this submission to check against next time

			########-------- Reply to Comments --------########
			logger.debug('Checking this submission\'s comments for Twitter links...')
			s.comments.replace_more(limit=None)
			# loop through all comments in this submission
			for comment in s.comments.list() :
				#logger.info('#### Comment id: %s (submission %s) ####',comment.id,comment.submission.id)# + '\n' + comment.body + '\n------------')
				# regex url to parse any url out of the given text;
				# the following regex pattern was taken from https://mathiasbynens.be/demo/url-regex (@gruber v2)
				# and modified to work in python; also added a check to not match * at the end
				# specifically in case a url is put in reddit italics/bold markup.
				# I uh... I hope this doesn't break any legit urls...
				# also added another '+' after the second '+' quantifier to make it possessive
				regex_url = r"(?i)\b((?:[a-z][\w-]+:(?:\/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]++[.][a-z]{2,4}\/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\"\*.,<>?«»“”‘’]))" # find any url
				regex_tweet = r"https?:\/\/(?:www\.|mobile\.)?twitter\.com\/\w{1,15}\/status\/\d+"

			    # Find urls in text; we use a separate process for this
				# simply so that we can time it out after a while;
				# since the regex is so unwieldy and the text unpredictable,
				# we run the risk of catastrophic backtracking;
				# I've done my best to stop that from happening, but
				queue = multiprocessing.Queue()
				p = multiprocessing.Process(target=findURLs, args=(regex_url, comment.body, queue))
				p.start()
				p.join(2) # Wait for 2 seconds or until process finishes
				# If thread is still active
				if p.is_alive():
				    logger.error("    Regex to find url on %s in %s was taking too long; skipping this comment",comment.id,comment.submission.id)
				    # Terminate
				    p.terminate()
				    p.join()
				try :
				    urls = queue.get_nowait()
				except queueError.Empty as e :
				    urls = []

				logger.debug('    Found the following URLs in this comment: %s', str(urls))
				# loop through any urls and see if any resolve into twitter status (tweet) links
				tweet_links = []
				for url in urls :
					url = url[0] # the list of urls is actually a list of tuples, and we just want the first string within the tuple, which is the url itself
					try :
						# follow any redirects and store that url
						session = requests.Session()
						resp = session.head(url, allow_redirects=True) # follow any redirects
						resolved_url = resp.url # save the redirected url
					except requests.exceptions.RequestException as e :
						logger.debug("    Using %s as found, problem with redirect detection: %s", url, str(e))
						resolved_url = url
					try :
						# test to see if the resolved url is a twitter link
						tweet_links.append(re.match(regex_tweet,resolved_url).group(0))
					except AttributeError as e :
						logger.debug('    no match to add to tweet_links in %s', resolved_url)
					except TypeError as e :
						logger.debug('    error appending tweet link: %s', str(e))
						#tweet_links.append(re.match(regex_tweet,url).group(0))
					#except :
				if tweet_links : # if tweet_links is not empty
					logger.info('#### Comment ID: %s (Submission %s) ####',comment.id,comment.submission.id)
					logger.info('    Found tweet links! (not commenting yet though) %s', str(tweet_links))

				# now loop through any twitter links we found in this comment
				# and post replies to them
				for tweet_link in tweet_links :
					# will have to modify alreadyDone() to be able to handle comments
					# particularly, it'll have to somehow handle the possibility of multiple replies
					# in the case that there are multiple links to reply to
					# if not alreadyDone(comment) :
					# 	composeReply(tweet_link, s.id, comment.id)
					pass


	except prawcore.exceptions.OAuthException as e:
		logger.critical('EXITING! Could not log in to reddit: %s',str(e))
		raise SystemExit('Quitting - could not log in to reddit') # if we can't deal with reddit, just stop altogether, and let it try again next time
	except prawcore.PrawcoreException as e:
		logger.critical('EXITING! Could not get subreddit/submissions: %s',str(e))
		raise SystemExit('Quitting - could not get subreddit/submissions') # if we can't deal with reddit, just stop altogether, and let it try again next time

# return True if we've already replied to this submission
def alreadyDone(s) :
	# First we'll check if we've commented in this thread already
	try:
		s.comments.replace_more(limit=None) # get unlimited list of comments
	except AttributeError as e:
		logger.error("ERROR: could not find comments in post (thread possibly too old?) - %s", str(e)) # found this bug when testing on very old threads
		return True # skip this post and move on to the next one

	for comment in s.comments : # loop through all the top-level comments
		# if we wrote this top-level comment
		try:
			if comment.author.name == botName :
				logger.debug('We posted a top-level comment on this thread already: %s', comment.id)
				return True
		except AttributeError as e:
			# logger.debug('attribute error: ' + str(e))
			# a comment will have no author if it has been deleted, which will raise an attribute error
			pass

	# We'll also check our comment log file to be extra sure (sometimes reddit posts are delayed,
	# so we want to do this to avoid a double post; one time the bot posted like 13 times in a row before I added this check)
	with open(paths.logs + 'comment_log.log') as log:
		for line in log:
			if line == s.id + '\n' :
				return True

	logger.debug('We have not commented on this post yet')
	return False

# compose comment from the contents of the tweet
# url is the url of the tweet
# sub_id is the id of the submission
# com_id is the id of the comment; if the link is from the submission itself
#		 rather than a comment within the submission, this should be left as None
def composeReply(url, sub_id, com_id = None) :
	# if com_ID isn't empty, we're replying to a comment
	if com_id is not None :
		where = "COMMENT"
		id = sub_id + "_" + com_id
	# otherwise, we're replying to a post (submission)
	else :
		where = "POST"
		id = sub_id

	logger.info("######## Found new tweet in %s ######## REDDIT:%s TWITTER:%s", where, id, url ) # log the submission id and twitter URL

	comment = None

	try:
		tweet = getTweet(url) # return tweet object
	except AttributeError as e: # we couldn't find the tweet id from the url
		logger.error("%s - %s",id,e.custom) # print custom error message
	except tweepy.error.TweepError as e: # we couldn't find the tweet from the id
		logger.error("%s - %s",id,e.custom) # print custom error message
	else:
		try:
			#raise Exception('Don\'t even try to get media while testing')
			tweetMedia = getTweetMedia(tweet) # find any media in the tweet and return as list
		except Exception as e:
			logger.error("%s - Could not post tweet due to exception when finding/rehosting media - message:%s",id,str(e), exc_info=True)
			if hasattr(e,'custom'):
				logger.error("%s - %s",id,e.custom) # print custom error message
		else:
			#logger.debug('title: %s',s.title)
			logger.debug('text: %s',tweet.full_text)

			# --- FORMAT COMMENT --- #
			lineSep = "--------------------"

			# Tweet author
			comment = "**[@" + tweet.user.screen_name + "](https://www.twitter.com/" + tweet.user.screen_name + ")** (" + tweet.user.name + "):\n\n"

			# Text
			tweetText = re.sub(r"\bhttps?:\/\/t\.co\/\w+\b",resolveLink(tweet), tweet.full_text, 0) # replace any t.co links in the tweet text with the resolved link; not only does this allow people to use them even if twitter is blocked, t.co links also probably cause reddit comments to be blocked as spam
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
							string = "error rehosting video. Sorry!"
						string = "Video: " + string
					else : # otherwise, we assume it's a string, a single url
						string = media
					comment += "* " + string + "\n\n"

			# Footer
			comment += lineSep + "\n\n"
			comment += "^I ^am ^a ^bot ^lubricated ^by ^Rick's ^slickness"
			comment += " ^| [^(message&nbsp;me)](https://www.reddit.com/message/compose?to=FleetFlotTheTweetBot)"
			comment += " ^| [^(source&nbsp;code)](https://github.com/JohnMTorgerson/FleetFlotTheTweetBot)"
			comment += " ^| ^Skål!"
	return comment


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
								filepath = download(url)
								response = g.upload_from_file(filepath)
								gfy_url = response.content_urls.mp4.url
							except GfypyException as e:
								# set custom error message and raise exception
								e.custom = 'Could not upload to gfycat. GfypyException: ' + str(e)
								raise
							except KeyError as e: # KeyError will be raised if we could connect to gfycat, but couldn't upload (e.g. the url we tried to upload was bad)
								# set custom error message and raise exception
								e.custom = 'Could not upload to gfycat. Probably a bad upload url. KeyError: ' + str(e) + ' doesn\'t exist in response. JSON response was: ' + str(response)
								raise
							except Exception as e:
								raise
							else:
								tweetMedia.append(gfy_url)
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
						except Exception as e:
							logger.error('Could not upload to Streamable, commenting anyway: %s',str(e))
							# send back an error message to be displayed in the comment
							vids = '*Sorry, there was an error trying to rehost a video in this tweet :(*'
							# we don't want to raise this exception, because we want to post the tweet
							# even if we couldn't get the video uploaded
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
	try:
		r = requests.get('https://api.streamable.com/import?url=' + url,auth=requests.auth.HTTPBasicAuth(login.loginStreamable.username,login.loginStreamable.password))
		shortcode = r.json()['shortcode'] # get shortcode from streamable for uploaded video, which we'll then check on to see if it got uploaded
	except Exception as e:
		e.custom = 'Streamable account may have been suspended; response was: ' + str(r)
		raise

	# wait until status is '2' or give up after 20 tries
	urls = {} # we'll return this
	tries = 20
	while tries > 0 :
		response = requests.get('https://api.streamable.com/videos/' + shortcode)
		response.json()
		status = response.json()['status']
		files = response.json()['files']
		if status == 2 : # success, but we still have to check to see if we have any url's yet
			if 'mp4' in files and files['mp4'].get('url','') != '' : # we have a desktop url
				urls['desktop'] = files['mp4']['url']
			if 'mp4-mobile' in files and files['mp4-mobile'].get('url','') != '' : # we have a mobile url
				urls['mobile'] = files['mp4-mobile']['url']

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

	# fix numbered list formatting by adding an escape like so: '5\.'
	# otherwise reddit will always change the numbers to start at 1
	string = re.sub(r"(?:(?<=^\d)|(?<=^\d{2})|(?<=^\d{3}))\.","\\.",string,0,re.MULTILINE)

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

# find urls in body of comment text; this function is called as a separate process
# in order to cut it off after a couple seconds in case of a runaway regex deal
def findURLs(pattern, text, return_queue) :
	return_queue.put(regex.findall(pattern,text)) # use the regex library instead of the re library because the regex_url pattern uses a possessive quantifier

def download(url) :
	try :
		req = requests.get(url)
		filename = 'temp/' + url.split('/')[-1]
		with open(filename,'wb') as file:
		    file.write(req.content)
	except Exception as e:
		e.custom = 'Unable to download file ' + url
		raise
	else :
		logger.debug('Successfully downloaded' + url + ' as ' + filename)
		return filename

if __name__ == "__main__":
    main()
