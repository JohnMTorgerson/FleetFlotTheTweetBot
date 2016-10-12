# Reddit
import praw
import loginReddit
def reddit():
    r = praw.Reddit(loginReddit.app_ua)
    r.set_oauth_app_info(loginReddit.app_id, loginReddit.app_secret, loginReddit.app_uri)
    r.refresh_access_information(loginReddit.app_refresh)
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