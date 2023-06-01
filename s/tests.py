import os
import tempfile
import pytest
import server
from contextlib import contextmanager
from server import is_valid_guid
from marshmallow import ValidationError
import redis


@pytest.fixture
def client():
    try:
        redis.Redis('localhost').flushdb()
    except redis.exceptions.ConnectionError:
        pass
    db_fd, db_path = tempfile.mkstemp()
    server.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    server.app.config['TESTING'] = True
    client = server.app.test_client()

    with server.app.app_context():
        server.db.create_all()

    yield client

    os.close(db_fd)
    os.unlink(db_path)

@contextmanager
def not_raises(exception):
  try:
    yield
  except exception:
    raise pytest.fail("DID RAISE {0}".format(exception))

def test_is_valid_guid():
    with not_raises(ValidationError):
        is_valid_guid('ABCDEF12345678999999999999999999')
    #non hex number
    with pytest.raises(ValidationError):
        is_valid_guid('GBCDEF12345678999999999999999999')
    #too long
    with pytest.raises(ValidationError):
        is_valid_guid('ABCDEF123456789999999999999999991')
    #too short
    with pytest.raises(ValidationError):
        is_valid_guid('ABCDEF1234567899999999999999999')
    with pytest.raises(ValidationError):
        is_valid_guid('')

def test_create(client):
    response = client.post('/guid', data='{"user":"john", "expire": 999}')
    assert response.status_code == 201
    guid = response.json['guid']
    response = client.get('/guid/'+guid)
    assert response.json['user'] == 'john'
    assert response.json['expire'] == 999
    assert response.status_code == 200

def test_create_already_exists(client):
    client.post('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"john", "expire": 999}')
    response = client.post('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"john", "expire": 999}')
    assert response.status_code == 400
    assert response.data == b'{"msg":"Error: GUID must be unique"}\n'

def test_create_missing_name(client):
    response = client.post('/guid', data='{"expire": 999}')
    assert response.status_code == 400
    assert response.data == b'{"user":["Missing data for required field."]}\n'

def test_read(client):
    client.post('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"john", "expire": 999}')
    # not cached
    response = client.get('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.json['user'] == 'john'
    assert response.json['expire'] == 999
    assert response.status_code == 200
    # cached path
    response = client.get('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.json['user'] == 'john'
    assert response.json['expire'] == 999
    assert response.status_code == 200

def test_read_missing(client):
    response = client.get('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.data == b'{"message":"GUID not found"}\n'
    assert response.status_code == 400

def test_update(client):
    client.post('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"john", "expire": 999}')
    client.put('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"bob", "expire": 1000}')
    response = client.get('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.json['user'] == 'bob'
    assert response.json['expire'] == 1000
    assert response.status_code == 200

def test_update_missing(client):
    response = client.put('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"bob", "expire": 1000}')
    assert response.data ==  b'{"message":"GUID not found"}\n'
    assert response.status_code == 400

def test_delete(client):
    client.post('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99',
        data='{"user":"john", "expire": 999}')
    client.delete('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    response = client.get('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.data ==  b'{"message":"GUID not found"}\n'
    assert response.status_code == 400

def test_delete_missing(client):
    response = client.delete('/guid/2C3D93F7A6EC4E4880F593D93DFCAB99')
    assert response.data ==  b'{"message":"GUID not found"}\n'
    assert response.status_code == 400
