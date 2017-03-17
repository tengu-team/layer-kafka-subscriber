import os
import json
import urllib
import jinja2
from flask import Flask, jsonify, request, abort, Response
from kafka import KafkaConsumer
from subprocess import Popen, call
from functools import wraps

app = Flask(__name__)
app.config.from_pyfile('credentials')

def check_auth(username, password):
    return username == app.config['USER'] and password == app.config['PASS']

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

class configuration(object):

    def __init__(self):
        if (os.path.exists('/home/ubuntu/kafka-helpers/kafkaip')):
            file = open('/home/ubuntu/kafka-helpers/kafkaip', 'r')
            self.kafkaip = file.read()
            file.close()

    def configure_kafka(self, kafkaip):
        self.kafkaip = kafkaip

    def start_consumer(self, endpoint, topics):
        self.stop_consumer(endpoint)
        if len(topics) > 0 and topics[0] != "":
            env_vars = [
                "topics={}".format(' '.join(topics)),
                "endpoint={}".format(endpoint),
                "kafkaip={}".format(self.kafkaip)
            ]
            self.render(source='/home/ubuntu/kafkasubscriber/templates/unitfile.consumer',
                        target='/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service',
                        context={
                            'description': 'Kafka consumer for ' + endpoint,
                            'env_vars': env_vars 
                        })
            call(["systemctl", "--user", "enable", "consumer-" + endpoint])
            call(["systemctl", "--user", "start", "consumer-" + endpoint])

    def stop_consumer(self, endpoint):
        if call(["systemctl", "--user", "-q", "is-active", "consumer-" + endpoint]) == 0: # 0 = active
            call(["systemctl", "--user", "stop", "consumer-" + endpoint])
            call(["systemctl", "--user", "disable", "consumer-" + endpoint])
        if os.path.exists('/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service'):
            os.remove('/home/ubuntu/.config/systemd/user/consumer-' + endpoint + '.service')
    
    def render(self, source, context, target):
        path, filename = os.path.split(source)
        with open(target, 'w+') as f:
            f.write(jinja2.Environment(
                    loader=jinja2.FileSystemLoader(path or './')
                    ).get_template(filename).render(context))
        
        
server_config = configuration()

@app.route('/subscribe', methods=['PUT'])
@requires_auth
def subscribe():
    if not request.json:
        abort(400)
    if request.json['topics'] and request.json['endpoint']:
        server_config.start_consumer(request.json['endpoint'], request.json['topics'])
    return jsonify({'status': 200})

@app.route('/unsubscribe', methods=['DELETE'])
@requires_auth
def unsubscribe():
    if not request.json:
        abort(400)
    if request.json['endpoint']:
        server_config.stop_consumer(request.json['endpoint'])
    return jsonify({'status': 200})

@app.route('/ping', methods=['GET'])
@requires_auth
def ping():
    resp = Response("pong")
    return resp

if __name__ == "__main__":
    app.run()