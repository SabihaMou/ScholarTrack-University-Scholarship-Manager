import os, secrets, csv, io
from pathlib import Path
from datetime import date, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, abort, send_file, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

db=SQLAlchemy(); lm=LoginManager(); csrf=CSRFProtect()
STATUSES=['Researching','Preparing','Submitted','Interview','Accepted','Rejected','Waitlisted']
class User(UserMixin,db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False); email=db.Column(db.String(180),unique=True,nullable=False); password=db.Column(db.String(256),nullable=False)
class Application(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); university=db.Column(db.String(160),nullable=False); program=db.Column(db.String(160),nullable=False); country=db.Column(db.String(90),default=''); degree=db.Column(db.String(60),default='Masters'); status=db.Column(db.String(30),default='Researching'); deadline=db.Column(db.Date); link=db.Column(db.String(500),default=''); notes=db.Column(db.Text,default='')
class Scholarship(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); application_id=db.Column(db.Integer,db.ForeignKey('application.id')); name=db.Column(db.String(160),nullable=False); amount=db.Column(db.String(100),default=''); status=db.Column(db.String(30),default='Researching'); deadline=db.Column(db.Date); link=db.Column(db.String(500),default=''); notes=db.Column(db.Text,default='')
class Document(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); application_id=db.Column(db.Integer,db.ForeignKey('application.id'),nullable=False); title=db.Column(db.String(120),nullable=False); filename=db.Column(db.String(180),default=''); stored=db.Column(db.String(180),default=''); completed=db.Column(db.Boolean,default=False)
class Task(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); application_id=db.Column(db.Integer,db.ForeignKey('application.id')); title=db.Column(db.String(160),nullable=False); due=db.Column(db.Date); done=db.Column(db.Boolean,default=False)
def dt(v):
 try:return date.fromisoformat(v) if v else None
 except ValueError:return None
def url(v):
 v=(v or '').strip();return v[:500] if v.startswith(('https://','http://')) else ''
def create_app(config=None):
 app=Flask(__name__,instance_relative_config=True)
 Path(app.instance_path).mkdir(parents=True,exist_ok=True)
 secret_path=Path(app.instance_path)/'secret.key'
 if not secret_path.exists():secret_path.write_text(secrets.token_hex(32),encoding='utf-8')
 app.config.update(SECRET_KEY=os.environ.get('SCHOLARTRACK_SECRET') or secret_path.read_text(encoding='utf-8').strip(),SQLALCHEMY_DATABASE_URI='sqlite:///'+str(Path(app.instance_path)/'data.sqlite3'),SQLALCHEMY_TRACK_MODIFICATIONS=False,MAX_CONTENT_LENGTH=8*1024*1024,UPLOAD_FOLDER=str(Path(app.instance_path)/'uploads'),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax')
 if config:app.config.update(config)
 Path(app.instance_path).mkdir(parents=True,exist_ok=True);Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True,exist_ok=True)
 db.init_app(app);lm.init_app(app);csrf.init_app(app);lm.login_view='login'
 with app.app_context():db.create_all()
 @lm.user_loader
 def load(uid):return db.session.get(User,int(uid))
 @app.context_processor
 def globals_():return dict(today=date.today(),statuses=STATUSES)
 def owned(model,id):
  item=db.session.get(model,id)
  if not item or item.user_id!=current_user.id:abort(404)
  return item
 def allof(model):return model.query.filter_by(user_id=current_user.id)
 @app.route('/')
 def index():return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))
 @app.route('/register',methods=['GET','POST'])
 def register():
  if current_user.is_authenticated:return redirect(url_for('dashboard'))
  if request.method=='POST':
   name=request.form.get('name','').strip()[:100];email=request.form.get('email','').strip().lower()[:180];password=request.form.get('password','')
   if not name or '@' not in email or len(password)<8:flash('Enter a name, valid email and password of at least 8 characters.','error')
   elif User.query.filter_by(email=email).first():flash('Email already registered.','error')
   else:
    u=User(name=name,email=email,password=generate_password_hash(password));db.session.add(u);db.session.commit();login_user(u);return redirect(url_for('dashboard'))
  return render_template('auth.html',register=True)
 @app.route('/login',methods=['GET','POST'])
 def login():
  if current_user.is_authenticated:return redirect(url_for('dashboard'))
  if request.method=='POST':
   u=User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
   if u and check_password_hash(u.password,request.form.get('password','')):login_user(u);return redirect(url_for('dashboard'))
   flash('Invalid email or password.','error')
  return render_template('auth.html',register=False)
 @app.post('/logout')
 @login_required
 def logout():logout_user();return redirect(url_for('login'))
 @app.route('/dashboard')
 @login_required
 def dashboard():
  apps=allof(Application).all();sch=allof(Scholarship).all();tasks=allof(Task).filter_by(done=False).all()
  upcoming=sorted([('University',a.university,a.deadline) for a in apps if a.deadline and a.deadline>=date.today()]+[('Scholarship',s.name,s.deadline) for s in sch if s.deadline and s.deadline>=date.today()]+[('Task',t.title,t.due) for t in tasks if t.due and t.due>=date.today()],key=lambda v:v[2])[:7]
  return render_template('dashboard.html',apps=apps,sch=sch,tasks=tasks,upcoming=upcoming,accepted=sum(a.status=='Accepted' for a in apps),submitted=sum(a.status in ['Submitted','Interview','Accepted','Rejected','Waitlisted'] for a in apps))
 @app.route('/applications')
 @login_required
 def applications():
  q=request.args.get('q','').strip();status=request.args.get('status','');query=allof(Application)
  if q:query=query.filter(db.or_(Application.university.ilike('%'+q+'%'),Application.program.ilike('%'+q+'%'),Application.country.ilike('%'+q+'%')))
  if status in STATUSES:query=query.filter_by(status=status)
  return render_template('applications.html',items=query.order_by(Application.id.desc()).all(),q=q,status=status)
 @app.route('/applications/new',methods=['GET','POST'])
 @app.route('/applications/<int:id>/edit',methods=['GET','POST'])
 @login_required
 def application_form(id=None):
  item=owned(Application,id) if id else None
  if request.method=='POST':
   uni=request.form.get('university','').strip()[:160];prog=request.form.get('program','').strip()[:160]
   if not uni or not prog:flash('University and program are required.','error')
   else:
    if item is None:item=Application(user_id=current_user.id);db.session.add(item)
    item.university=uni;item.program=prog;item.country=request.form.get('country','')[:90];item.degree=request.form.get('degree','Masters')[:60];item.status=request.form.get('status') if request.form.get('status') in STATUSES else 'Researching';item.deadline=dt(request.form.get('deadline'));item.link=url(request.form.get('link'));item.notes=request.form.get('notes','')[:5000];db.session.commit();flash('Application saved.','success');return redirect(url_for('application_detail',id=item.id))
  return render_template('application_form.html',item=item)
 @app.route('/applications/<int:id>')
 @login_required
 def application_detail(id):
  return render_template('detail.html',item=owned(Application,id),docs=allof(Document).filter_by(application_id=id).all(),sch=allof(Scholarship).filter_by(application_id=id).all())
 @app.post('/applications/<int:id>/delete')
 @login_required
 def application_delete(id):
  item=owned(Application,id)
  for doc in allof(Document).filter_by(application_id=id).all():
   if doc.stored:(Path(app.config['UPLOAD_FOLDER'])/doc.stored).unlink(missing_ok=True)
   db.session.delete(doc)
  for s in allof(Scholarship).filter_by(application_id=id):s.application_id=None
  for t in allof(Task).filter_by(application_id=id):t.application_id=None
  db.session.delete(item);db.session.commit();flash('Application deleted.','success');return redirect(url_for('applications'))
 @app.route('/scholarships')
 @login_required
 def scholarships():return render_template('scholarships.html',items=allof(Scholarship).order_by(Scholarship.id.desc()).all())
 @app.route('/scholarships/new',methods=['GET','POST'])
 @app.route('/scholarships/<int:id>/edit',methods=['GET','POST'])
 @login_required
 def scholarship_form(id=None):
  item=owned(Scholarship,id) if id else None;apps=allof(Application).all()
  if request.method=='POST':
   name=request.form.get('name','').strip()[:160]
   if not name:flash('Scholarship name required.','error')
   else:
    if item is None:item=Scholarship(user_id=current_user.id);db.session.add(item)
    aid=request.form.get('application_id',type=int);item.application_id=aid if aid and any(a.id==aid for a in apps) else None
    item.name=name;item.amount=request.form.get('amount','')[:100];item.status=request.form.get('status') if request.form.get('status') in STATUSES else 'Researching';item.deadline=dt(request.form.get('deadline'));item.link=url(request.form.get('link'));item.notes=request.form.get('notes','')[:5000];db.session.commit();flash('Scholarship saved.','success');return redirect(url_for('scholarships'))
  return render_template('scholarship_form.html',item=item,apps=apps)
 @app.post('/scholarships/<int:id>/delete')
 @login_required
 def scholarship_delete(id):db.session.delete(owned(Scholarship,id));db.session.commit();return redirect(url_for('scholarships'))
 @app.post('/applications/<int:id>/documents')
 @login_required
 def document_add(id):
  owned(Application,id);title=request.form.get('title','').strip()[:120]
  if not title:flash('Document title required.','error');return redirect(url_for('application_detail',id=id))
  f=request.files.get('file');filename='';stored=''
  if f and f.filename:
   filename=secure_filename(f.filename);ext=filename.rsplit('.',1)[-1].lower() if '.' in filename else ''
   if ext not in {'pdf','png','jpg','jpeg','doc','docx','txt'}:flash('Unsupported file type.','error');return redirect(url_for('application_detail',id=id))
   stored=secrets.token_hex(20)+'.'+ext;f.save(Path(app.config['UPLOAD_FOLDER'])/stored)
  db.session.add(Document(user_id=current_user.id,application_id=id,title=title,filename=filename,stored=stored,completed=bool(stored) or request.form.get('completed')=='on'));db.session.commit();return redirect(url_for('application_detail',id=id))
 @app.post('/documents/<int:id>/toggle')
 @login_required
 def document_toggle(id):d=owned(Document,id);d.completed=not d.completed;db.session.commit();return redirect(url_for('application_detail',id=d.application_id))
 @app.post('/documents/<int:id>/delete')
 @login_required
 def document_delete(id):
  d=owned(Document,id);aid=d.application_id
  if d.stored:(Path(app.config['UPLOAD_FOLDER'])/d.stored).unlink(missing_ok=True)
  db.session.delete(d);db.session.commit();return redirect(url_for('application_detail',id=aid))
 @app.route('/documents/<int:id>/download')
 @login_required
 def document_download(id):
  d=owned(Document,id)
  if not d.stored:abort(404)
  return send_file(Path(app.config['UPLOAD_FOLDER'])/d.stored,as_attachment=True,download_name=d.filename)
 @app.route('/tasks',methods=['GET','POST'])
 @login_required
 def tasks():
  if request.method=='POST':
   title=request.form.get('title','').strip()[:160];aid=request.form.get('application_id',type=int)
   if aid and not allof(Application).filter_by(id=aid).first():aid=None
   if title:db.session.add(Task(user_id=current_user.id,title=title,due=dt(request.form.get('due')),application_id=aid));db.session.commit()
   return redirect(url_for('tasks'))
  return render_template('tasks.html',items=allof(Task).order_by(Task.done.asc(),Task.due.asc()).all(),apps=allof(Application).all())
 @app.post('/tasks/<int:id>/toggle')
 @login_required
 def task_toggle(id):t=owned(Task,id);t.done=not t.done;db.session.commit();return redirect(url_for('tasks'))
 @app.post('/tasks/<int:id>/delete')
 @login_required
 def task_delete(id):db.session.delete(owned(Task,id));db.session.commit();return redirect(url_for('tasks'))
 @app.route('/calendar')
 @login_required
 def calendar():
  entries=[dict(name=a.university,day=a.deadline,kind='University') for a in allof(Application) if a.deadline]+[dict(name=s.name,day=s.deadline,kind='Scholarship') for s in allof(Scholarship) if s.deadline]+[dict(name=t.title,day=t.due,kind='Task') for t in allof(Task) if t.due and not t.done]
  return render_template('calendar.html',entries=sorted(entries,key=lambda x:x['day']))
 @app.route('/analytics')
 @login_required
 def analytics():
  apps=allof(Application).all();status={s:sum(a.status==s for a in apps) for s in STATUSES};country={c:sum(a.country==c for a in apps) for c in sorted(set(a.country for a in apps if a.country))}
  return render_template('analytics.html',status=status,country=country,total=len(apps))
 @app.route('/export.csv')
 @login_required
 def export_csv():
  out=io.StringIO();writer=csv.writer(out);writer.writerow(['University','Program','Country','Degree','Status','Deadline','Website','Notes'])
  for a in allof(Application):writer.writerow([a.university,a.program,a.country,a.degree,a.status,a.deadline or '',a.link,a.notes])
  return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=scholartrack_applications.csv'})
 @app.post('/demo/load')
 @login_required
 def demo_load():
  if allof(Application).count():flash('Demo data is available only for empty accounts.','error');return redirect(url_for('dashboard'))
  for uni,prog,country,status,days in [('Northbridge University','MSc Computer Science','United Kingdom','Preparing',21),('Westlake Institute','MSc Data Science','Canada','Submitted',42),('Pacific Tech University','MSc Artificial Intelligence','Australia','Researching',65),('Greenfield University','MSc Software Engineering','Germany','Accepted',-7)]:
   a=Application(user_id=current_user.id,university=uni,program=prog,country=country,status=status,deadline=date.today()+timedelta(days=days));db.session.add(a);db.session.flush()
   for title,done in [('CV',True),('Transcript',True),('Study plan',False),('Recommendation letter',False)]:db.session.add(Document(user_id=current_user.id,application_id=a.id,title=title,completed=done))
  db.session.add(Scholarship(user_id=current_user.id,name='Global Excellence Award',amount='Full tuition',status='Preparing',deadline=date.today()+timedelta(days=28)))
  db.session.add(Task(user_id=current_user.id,title='Finish study plan',due=date.today()+timedelta(days=4)));db.session.commit();flash('Fictional demo records added.','success');return redirect(url_for('dashboard'))
 @app.errorhandler(413)
 def too_large(e):return 'Upload too large (8 MB limit).',413
 return app
if __name__=='__main__':
 app=create_app();print('Open http://127.0.0.1:5000 in your browser');app.run(host='127.0.0.1',port=5000,debug=False)
