# Reddit
import praw
import loginReddit
def reddit():
    r = praw.Reddit(client_id=loginReddit.app_id,
                     client_secret=loginReddit.app_secret,
                     password=loginReddit.password,
                     user_agent=loginReddit.app_ua,
                     username=loginReddit.username)
    return r

# Twitter
import tweepy
import loginTwitter
def twitter() :
	auth = tweepy.OAuthHandler(loginTwitter.consumer_key, loginTwitter.consumer_secret)
	auth.set_access_token(loginTwitter.access_token, loginTwitter.access_secret)
	t = tweepy.API(auth)
	return t

# Imgur
from imgurpython import ImgurClient
import loginImgur
def imgur() :
	i = ImgurClient(loginImgur.app_id, loginImgur.app_secret)
	return i

# Streamable (in this case, we just need to get the username and password,
#            which will be passed as a BasicAuth request at the time of upload)
import loginStreamable
