import os,tempfile,pytest
from app import app,init_db
@pytest.fixture()
def client():
 fd,path=tempfile.mkstemp();os.close(fd);app.config.update(TESTING=True,DATABASE=path)
 with app.app_context():init_db()
 with app.test_client() as c:yield c
 os.unlink(path)
def test_home(client):assert client.get('/').status_code==200
def test_history(client):assert client.get('/api/history').json==[]
def test_empty_message(client):assert client.post('/api/chat',json={'message':''}).status_code==400
def test_missing_api_key(client,monkeypatch):
 monkeypatch.delenv('GEMINI_API_KEY',raising=False);assert client.post('/api/chat',json={'message':'Hello'}).status_code==503
