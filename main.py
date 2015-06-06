from app import app, database

from models import *
from views import *

def create_tables():
    database.create_tables([User, Entry,
                            FTSEntry, Comment, 
                            Tag], safe=True)
                                     
if __name__ == '__main__':
	create_tables()
	app.run(debug=True)