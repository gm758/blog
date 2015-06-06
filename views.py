import functools
import urllib

from flask import (abort, flash, Markup, redirect, render_template,
                   request, Response, session, url_for)
                   
from app import app
from models import *

def login_required(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        if session.get('logged_in'):
            return fn(*args, **kwargs)
        return redirect(url_for('login', next=request.path))
    return inner

@app.route('/login/', methods=['GET','POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next')
    if request.method == 'POST' and request.form.get('password'):
        username = request.form.get('username')
        password = request.form.get('password')
        if request.form.get('setpw') or False:
            user = User.create(
                     username=username,
                     password=password)
            session['logged_in'] = True
            session.permanent = True
            flash('User successfully created', 'success')
            return redirect(next_url or url_for('index'))
        elif User.verify(username, password):
            session['logged_in'] = True
            session.permanent = True
            flash('You are now logged in.', 'success')
            return redirect(next_url or url_for('index'))
        else:
            flash('Incorrect password.', 'danger')

    return render_template('login.html', next_url = next_url)

@app.route('/logout/', methods=['GET','POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        return redirect(url_for('login'))
    return render_template('logout.html')

@app.route('/')
def index():
    search_query = request.args.get('q')
    if search_query:
        #needs to be updated to handle tags, comments
        query = Entry.search(search_query)
    else:
        query = Entry.public().order_by(Entry.timestamp.desc())
    return object_list('index.html', query, search=search_query, title="Blog Entries")

@app.route('/tags/')
def tags():
    query = Tag.select(Tag, fn.Count().alias('count')).group_by(Tag.tag).order_by(Tag.tag)
    return object_list('index.html', query)

@app.route('/tags/<tag>/')
def tag_search(tag):
    query = Entry.tagsearch(tag).order_by(Entry.timestamp.desc())
    return object_list('index.html', query, title="Entries tagged with %s" % tag)

@app.route('/drafts/')
@login_required
def drafts():
    query = Entry.drafts().order_by(Entry.timestamp.desc())
    return object_list('index.html', query, title="Drafts")

@app.route('/comments/', methods=['GET','POST'])
@login_required
def comments():
    query = Comment.select().where(Comment.approved == False).order_by(Comment.timestamp.desc()) 
    if request.method == 'POST':
        f = request.form
        for key in f.keys():
            #In the future, I'd like to classify these as spam/ham rather than just approve/delete
            if int(f[key]):
                Comment.update(approved=True).where(Comment.id == int(key)).execute()
            else:
                Comment.delete().where(Comment.id == int(key)).execute()
    return object_list('comments.html', query)



@app.route('/create/', methods=['GET','POST'])
@login_required
def create():
    if request.method == 'POST':
        if request.form.get('title') and request.form.get('content'):
            entry = Entry.create(
                title=request.form['title'],
                content=request.form['content'],
                published=request.form.get('published') or False)
            tags = request.form['tags'].split()
            for tag in tags:
                Tag.create(tag=tag, post=entry)

            flash('Entry created successfully', 'success')
            if entry.published:
                return redirect(url_for('detail', slug=entry.slug))
            else:
                return redirect(url_for('edit', slug=entry.slug))
        else:
            flash('Title and content are required.', 'danger')
    return render_template('create.html')

@app.route('/<slug>/', methods=['GET','POST'])
def detail(slug):
    if session.get('logged_in'):
        query = Entry.select()
    else:
        query = Entry.public()
    entry = get_object_or_404(query, Entry.slug == slug)
    tags = Tag.select().where(Tag.post == entry)
    comments = Comment.select().where(Comment.approved == True, Comment.post == entry)
    #adding comments to posts
    if request.method  == 'POST':
        #add name, email and content requirements
        if request.form.get('comment'):
            comment = Comment.create(
                name=request.form['name'],
                email=request.form['email'],
                content=request.form['comment'],
                approved=False,
                post=entry)
            flash('Comment posted successfully', 'success')
            return redirect(url_for('detail', slug=entry.slug))
        else:
            flash('Your comment is empty')
    return render_template('detail.html', entry=entry, tags = tags, comments=comments)

@app.route('/<slug>/edit/', methods=['GET', 'POST'])
@login_required
def edit(slug):
    entry = get_object_or_404(Entry, Entry.slug == slug)
    if request.method == 'POST':
        if request.form.get('title') and request.form.get('content'):
            entry.title = request.form['title']
            entry.content = request.form['content']
            entry.published = request.form.get('published') or False

            flash('Entry saved successfully.', 'success')
            if entry.published:
                return redirect(url_for('detail', slug=entry.slug))
            else:
                return redirect(url_for('edit', slug=entry.slug))
        else:
            flash('Title and content are required.', 'danger')
    return render_template('edit.html', entry=entry)


@app.template_filter('clean_querystring')
def clean_querystring(request_args, *keys_to_remove, **new_values):
    querystring = dict((key, value) for key, value in request_args.items())
    for key in keys_to_remove:
        querystring.pop(key, None)
    querystring.update(new_values)
    return urllib.urlencode(querystring)

@app.errorhandler(404)
def not_found(exc):
    return Response('<h3>Page not found</h3>'), 404
