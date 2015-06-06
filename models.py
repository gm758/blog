#Database models for use with ORM (peewee)
import datetime
from hashlib import md5
import re

from peewee import *
from playhouse.flask_utils import get_object_or_404, object_list
from playhouse.sqlite_ext import *
from werkzeug.security import generate_password_hash, check_password_hash
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache

from flask import current_app, Markup
from app import flask_db, database

oembed_providers = bootstrap_basic(OEmbedCache())


class User(flask_db.Model):
    username = CharField()
    password = CharField()
    
    def save(self, *args, **kwargs):
        print self.password
        self.password = generate_password_hash(self.password)
        ret = super(User, self).save(*args, **kwargs)
        return ret
    
    @classmethod
    def verify(cls, username, password):
        pw_hash = User.select(User.password).where(User.username == username)
        return check_password_hash(pw_hash, password)
    

class Entry(flask_db.Model):
    title = CharField()
    slug = CharField(unique=True)
    content = TextField()
    published = BooleanField(index=True)
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = re.sub('[^\w]+', '-', self.title.lower())
        ret = super(Entry, self).save(*args, **kwargs)

        self.update_search_index()
        return ret
    
    def update_search_index(self):
        try:
            fts_entry = FTSEntry.get(FTSEntry.entry_id == self.id)
        except FTSEntry.DoesNotExist:
            fts_entry = FTSEntry(entry_id=self.id)
            force_insert = True
        else:
            force_insert = False
        fts_entry.content = '\n'.join((self.title, self.content))
        fts_entry.save(force_insert=force_insert)

    @classmethod
    def _query_all(cls):
        return (Entry.select(Entry, Tag, fn.Count(fn.Distinct(Comment.id)).alias('count')).join(Tag, JOIN.LEFT_OUTER).switch(Entry).join(Comment, JOIN.LEFT_OUTER))

    @classmethod
    def public(cls):
        return cls._query_all().where(Entry.published == True).group_by(Entry.id)

    @classmethod
    def tagsearch(cls, tag):
        return cls._query_all().where(Entry.published == True, Tag.tag == tag).group_by(Entry.id)

    @classmethod
    def drafts(cls):
        return cls._query_all().where(Entry.published == False).group_by(Entry.id)

    @classmethod
    def search(cls, query):
        words = [word.strip() for word in query.split() if word.strip()]
        if not words:
            #Return empty query
            return Entry.select().where(Entry.id == 0)
        else:
            search = ' '.join(words)

        return (FTSEntry
                .select(
                    FTSEntry,
                    Entry,
                    FTSEntry.rank().alias('score'))
                .join(Entry, on=(FTSEntry.entry_id == Entry.id).alias('entry'))
                .where(
                    (Entry.published == True) &
                    (FTSEntry.match(search))
                .order_by(SQL('score').desc())))

    @property
    def html_content(self):
        hilite = CodeHiliteExtension(linenums=False, css_class='highlight')
        extras = ExtraExtension()
        markdown_content = markdown(self.content, extensions=[hilite, extras])
        oembed_content = parse_html(
            markdown_content,
            oembed_providers,
            urlize_all=True,
            maxwidth=current_app.config['SITE_WIDTH'])
        return Markup(oembed_content)

class FTSEntry(FTSModel):
    entry_id = IntegerField(Entry)
    content = TextField()

    class Meta:
        database = database

class Comment(flask_db.Model):
    name = CharField()
    email = CharField()
    content = TextField()
    approved = BooleanField(index=True)
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)
    post = ForeignKeyField(Entry, related_name='comments')

    def avatar(self, size):
        return 'http://www.gravatar.com/avatar/%s?d=mm&s=%d' % (md5(self.email.encode('utf-8')).hexdigest(), size)

#In the future, it may be worthwhile to split this into two tables
#A table containing only tag CharField
#and a table containing relationships between comments and Tags
class Tag(flask_db.Model):
    tag = CharField()
    post = ForeignKeyField(Entry, related_name="tags")