from pritunl import settings
from pritunl import utils
from pritunl import app

import flask
import datetime

@app.app.route('/ping', methods=['GET'])
def ping_get():
    ping_timestamp = settings.local.host_ping_timestamp
    host_ttl = datetime.timedelta(seconds=settings.app.host_ttl)

    if ping_timestamp and utils.now() > ping_timestamp + host_ttl:
        raise flask.abort(504)
    else:
        return utils.response()
