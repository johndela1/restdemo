import os
import re
from redis import Redis
from uuid import uuid4
from datetime import datetime, timedelta
from json import loads
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from sqlalchemy.exc import IntegrityError

from marshmallow import fields, validate, ValidationError

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'guid.sqlite')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
ma = Marshmallow(app)
cache = Redis()
# consider setting the following
try:
    pass
    # this should be set according to the access distribution; lru may not be best
    # cache.config_set('maxmemory-policy', 'allkeys-lru')
    # arbitrarily set to 1 MB
    # cache.config_set('maxmemory', 1024*1024)
except redis.exceptions.ConnectionError:
    pass


def is_valid_guid(guid):
    if not len(guid) == 32 or re.fullmatch(r"[\dA-F]+", guid or "") is None:
        raise ValidationError(
            'GUID must be 32 hexadecimal characters, all uppercase'
        )

class Record(db.Model):
    guid = db.Column(db.String(32), primary_key=True)
    user = db.Column(db.String(80))
    expire = db.Column(db.Integer)

    def __init__(self, guid, user, expire):
        self.guid = guid
        self.user = user
        self.expire = expire


class RecordSchema(ma.Schema):
    guid = fields.String(validate=is_valid_guid)
    user = fields.String(required=True, validate=validate.Length(3))
    expire = fields.Integer()


rec_schema = RecordSchema()

# endpoint to create new record
@app.route("/guid", defaults={'guid':None}, methods=["POST"])
@app.route("/guid/<guid>", methods=["POST"])
def create(guid):
    json_data = request.get_json(force=True)
    if guid is not None:
        json_data['guid'] = guid
    # Validate and deserialize input
    data, errors = rec_schema.load(json_data)
    if errors:
           return jsonify(errors), 400

    guid = data.get('guid', uuid4().hex.upper())
    user = data['user']
    expire = data.get('expire',
        int((datetime.now() + timedelta(days=30)).timestamp()))
    new_rec = Record(guid, user, expire)
    db.session.add(new_rec)
    try:
        db.session.commit()
    except IntegrityError:
           return jsonify(msg='Error: GUID must be unique'), 400
    return rec_schema.jsonify(new_rec), 201

# endpoint to get record detail by guid
@app.route("/guid/<guid>", methods=["GET"])
def read(guid):
    try:
        cached = cache.get(guid)
        if cached:
            return jsonify(loads(cached))
    except redis.exceptions.ConnectionError:
        pass

    rec = Record.query.get(guid)
    if rec is None:
        return jsonify({'message': 'GUID not found'}), 400
    response = rec_schema.jsonify(rec)
    try:
        cache.set(guid, response.data)
    except redis.exceptions.ConnectionError:
        pass
    return response

# endpoint to update record
@app.route("/guid/<guid>", methods=["PUT"])
def update(guid):
    json_data = request.get_json(force=True)
    if not json_data:
            return jsonify({'message': 'No input data provided.'}), 400
    data, errors = rec_schema.load(json_data, partial=('user',))
    if errors:
           return jsonify(errors), 400

    rec = Record.query.get(guid)
    if rec is None:
        return jsonify({'message': 'GUID not found'}), 400
    rec.user = data.get('user', rec.user)
    rec.expire = data.get('expire', rec.expire)

    db.session.commit()
    try:
        cache.delete(rec.guid)
    except redis.exceptions.ConnectionError:
        pass
    return rec_schema.jsonify(rec)

# endpoint to delete record
@app.route("/guid/<guid>", methods=["DELETE"])
def delete(guid):
    rec = Record.query.get(guid)
    if rec is None:
        return jsonify({'message': 'GUID not found'}), 400
    db.session.delete(rec)
    db.session.commit()
    try:
        cache.delete(rec.guid)
    except redis.exceptions.ConnectionError:
        pass
    return '', 200

# endpoint to show all record, needs pagination
recs_schema = RecordSchema(many=True)
@app.route("/guid", methods=["GET"])
def recs():
    all_recs = Record.query.all()
    result = recs_schema.dump(all_recs)
    return jsonify(result.data)

if __name__ == '__main__':
    app.run(debug=False)
