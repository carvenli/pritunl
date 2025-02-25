from pritunl.constants import *
from pritunl import app
from pritunl import host
from pritunl import utils
from pritunl import logger
from pritunl import event
from pritunl import auth

import flask

@app.app.route('/host', methods=['GET'])
@app.app.route('/host/<hst>', methods=['GET'])
@auth.session_auth
def host_get(hst=None):
    if hst:
        return utils.jsonify(host.get_by_id(hst).dict())

    hosts = []
    page = flask.request.args.get('page', None)
    page = int(page) if page else page

    for hst in host.iter_hosts_dict(page=page):
        hosts.append(hst)

    if page is not None:
        return utils.jsonify({
            'page': page,
            'page_total': host.get_host_page_total(),
            'hosts': hosts,
        })
    else:
        return utils.jsonify(hosts)

@app.app.route('/host/<hst>', methods=['PUT'])
@auth.session_auth
def host_put(hst=None):
    hst = host.get_by_id(hst)

    if 'name' in flask.request.json:
        hst.name = utils.filter_str(
            flask.request.json['name']) or utils.random_name()

    if 'public_address' in flask.request.json:
        hst.public_address = utils.filter_str(
            flask.request.json['public_address'])

    if 'link_address' in flask.request.json:
        hst.link_address = utils.filter_str(
            flask.request.json['link_address'])

    hst.commit(hst.changed)
    event.Event(type=HOSTS_UPDATED)

    return utils.jsonify(hst.dict())

@app.app.route('/host/<hst>', methods=['DELETE'])
@auth.session_auth
def host_delete(hst):
    hst = host.get_by_id(hst)
    hst.remove()

    logger.LogEntry(message='Deleted host "%s".' % hst.name)
    event.Event(type=HOSTS_UPDATED)

    return utils.jsonify({})

@app.app.route('/host/<hst>/usage/<period>', methods=['GET'])
@auth.session_auth
def host_usage_get(hst, period):
    hst = host.get_by_id(hst)
    return utils.jsonify(hst.usage.get_period(period))
