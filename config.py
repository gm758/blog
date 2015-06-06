#config
import os

class Configuration(object):
    APP_DIR = os.path.dirname(os.path.realpath(__file__))
    DATABASE = 'sqliteext:///%s' % os.path.join(APP_DIR, 'blog.db')
    DEBUG = False
    SECRET_KEY = 'secret_key_goes_here'
    SITE_WIDTH = 800