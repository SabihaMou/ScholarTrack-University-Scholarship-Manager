import io
import pytest
from app import create_app, db, User, Application, Scholarship, Document

@pytest.fixture
def client(tmp_path):
    app=create_app({'TESTING':True,'WTF_CSRF_ENABLED':False,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'test.db'),'UPLOAD_FOLDER':str(tmp_path/'uploads')})
    with app.test_client() as c:yield c

def register(c,email='alex@example.com'):
    return c.post('/register',data={'name':'Alex','email':email,'password':'strongpassword'},follow_redirects=True)

def test_auth(client):
    assert client.get('/dashboard').status_code==302
    assert b'Big dreams' in register(client).data
    client.post('/logout')
    assert b'Invalid email' in client.post('/login',data={'email':'alex@example.com','password':'wrong'},follow_redirects=True).data
    assert client.post('/login',data={'email':'alex@example.com','password':'strongpassword'}).status_code==302

def test_application_crud_and_export(client):
    register(client)
    r=client.post('/applications/new',data={'university':'Example University','program':'MSc CS','status':'Preparing','deadline':'2027-03-10'})
    assert r.status_code==302
    assert b'Example University' in client.get('/applications').data
    assert b'Example University' in client.get('/export.csv').data
    assert b'MSc CS' in client.get('/applications/1').data
    client.post('/applications/1/edit',data={'university':'Updated University','program':'MSc AI','status':'Submitted'})
    assert b'Updated University' in client.get('/applications').data
    client.post('/applications/1/delete')
    assert b'Updated University' not in client.get('/applications').data

def test_scholarship_tasks_and_demo(client):
    register(client)
    client.post('/scholarships/new',data={'name':'Merit Award','amount':'100%','status':'Preparing'})
    assert b'Merit Award' in client.get('/scholarships').data
    client.post('/tasks',data={'title':'Finish CV','due':'2027-02-01'})
    assert b'Finish CV' in client.get('/tasks').data
    client.post('/tasks/1/toggle')
    client.post('/scholarships/1/delete')
    assert b'Merit Award' not in client.get('/scholarships').data
    client.post('/demo/load')
    assert b'Northbridge University' in client.get('/dashboard').data
    assert client.get('/analytics').status_code==200
    assert client.get('/calendar').status_code==200

def test_upload_and_user_isolation(client):
    register(client)
    client.post('/applications/new',data={'university':'Private University','program':'MSc'})
    response=client.post('/applications/1/documents',data={'title':'CV','file':(io.BytesIO(b'%PDF-1.4 example'),'cv.pdf')},content_type='multipart/form-data')
    assert response.status_code==302
    assert client.get('/documents/1/download').data==b'%PDF-1.4 example'
    client.post('/logout')
    register(client,'other@example.com')
    assert client.get('/applications/1').status_code==404
    assert client.get('/documents/1/download').status_code==404
    assert client.post('/applications/1/delete').status_code==404
    assert b'Private University' not in client.get('/export.csv').data

def test_upload_extension_blocked(client):
    register(client)
    client.post('/applications/new',data={'university':'University','program':'MSc'})
    r=client.post('/applications/1/documents',data={'title':'Unsafe','file':(io.BytesIO(b'bad'),'evil.exe')},content_type='multipart/form-data',follow_redirects=True)
    assert b'Unsupported file type' in r.data
