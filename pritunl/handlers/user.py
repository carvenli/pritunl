from pritunl.constants import *
from pritunl.exceptions import *
from pritunl import settings
from pritunl import utils
from pritunl import logger
from pritunl import event
from pritunl import server
from pritunl import organization
from pritunl import app
from pritunl import auth
from pritunl import mongo

import flask
import time

@app.app.route('/user/<org_id>', methods=['GET'])
@app.app.route('/user/<org_id>/<user_id>', methods=['GET'])
@app.app.route('/user/<org_id>/<int:page>', methods=['GET'])
@auth.session_auth
def user_get(org_id, user_id=None, page=None):
    org = organization.get_by_id(org_id)
    if user_id:
        return utils.jsonify(org.get_user(user_id).dict())

    page = flask.request.args.get('page', None)
    page = int(page) if page else page
    search = flask.request.args.get('search', None)
    limit = int(flask.request.args.get('limit', settings.user.page_count))
    otp_auth = False
    server_count = 0
    servers = []

    for svr in org.iter_servers(fields=('name', 'otp_auth')):
        servers.append(svr)
        server_count += 1
        if svr.otp_auth:
            otp_auth = True

    users = []
    users_id = []
    users_data = {}
    users_servers = {}
    fields = (
        'organization',
        'organization_name',
        'name',
        'email',
        'type',
        'otp_secret',
        'disabled',
    )
    for usr in org.iter_users(page=page, search=search,
            search_limit=limit, fields=fields):
        users_id.append(usr.id)

        user_dict = usr.dict()
        user_dict['status'] = False
        user_dict['otp_auth'] = otp_auth

        users_data[usr.id] = user_dict
        users_servers[usr.id] = {}

        server_data = []
        for svr in servers:
            data = {
                'id': svr.id,
                'name': svr.name,
                'status': False,
                'client_id': None,
                'device_name': None,
                'platform': None,
                'real_address': None,
                'virt_address': None,
                'connected_since': None
            }
            server_data.append(data)
            users_servers[usr.id][svr.id] = data

        user_dict['servers'] = sorted(server_data, key=lambda x: x['name'])

        users.append(user_dict)

    clients_collection = mongo.get_collection('clients')
    for doc in clients_collection.find({
                'user_id': {'$in': users_id},
            }):
        server_data = users_servers[doc['user_id']].get(doc['server_id'])
        if not server_data:
            continue

        users_data[doc['user_id']]['status'] = True

        server_data['status'] = True
        server_data['client_id'] = doc['_id']
        server_data['device_name'] = doc['device_name']
        server_data['platform'] = doc['platform']
        server_data['real_address'] = doc['real_address']
        server_data['virt_address'] = doc['virt_address'].split('/')[0]
        server_data['connected_since'] = doc['connected_since']

    ip_addrs_iter = server.multi_get_ip_addr(org_id, users_id)
    for user_id, server_id, ip_add in ip_addrs_iter:
        server_data = users_servers[user_id].get(server_id)
        if server_data and not server_data['virt_address']:
            server_data['virt_address'] = ip_add

    if page is not None:
        return utils.jsonify({
            'page': page,
            'page_total': org.page_total,
            'server_count': server_count,
            'users': users,
        })
    elif search is not None:
        return utils.jsonify({
            'search': search,
            'search_more': limit < org.last_search_count,
            'search_limit': limit,
            'search_count': org.last_search_count,
            'search_time':  round((time.time() - flask.g.start), 4),
            'server_count': server_count,
            'users': users,
        })
    else:
        return utils.jsonify(users)

@app.app.route('/user/<org_id>', methods=['POST'])
@auth.session_auth
def user_post(org_id):
    org = organization.get_by_id(org_id)
    users = []

    if isinstance(flask.request.json, list):
        users_data = flask.request.json
    else:
        users_data = [flask.request.json]

    for user_data in users_data:
        name = utils.filter_str(user_data['name'])
        email = utils.filter_str(user_data.get('email'))
        disabled = user_data.get('disabled')
        user = org.new_user(type=CERT_CLIENT, name=name, email=email,
            disabled=disabled)
        users.append(user.dict())

    event.Event(type=ORGS_UPDATED)
    event.Event(type=USERS_UPDATED, resource_id=org.id)
    event.Event(type=SERVERS_UPDATED)

    if isinstance(flask.request.json, list):
        logger.LogEntry(message='Created %s new users.' % len(
            flask.request.json))
        return utils.jsonify(users)
    else:
        logger.LogEntry(message='Created new user "%s".' % users[0]['name'])
        return utils.jsonify(users[0])

@app.app.route('/user/<org_id>/<user_id>', methods=['PUT'])
@auth.session_auth
def user_put(org_id, user_id):
    org = organization.get_by_id(org_id)
    user = org.get_user(user_id)

    if 'name' in flask.request.json:
        user.name = utils.filter_str(flask.request.json['name']) or None

    if 'email' in flask.request.json:
        user.email = utils.filter_str(flask.request.json['email']) or None

    disabled = flask.request.json.get('disabled')
    if disabled is not None:
        user.disabled = disabled

    user.commit()
    event.Event(type=USERS_UPDATED, resource_id=user.org.id)

    if disabled:
        user.disconnect()
        if user.type == CERT_CLIENT:
            logger.LogEntry(message='Disabled user "%s".' % user.name)
    elif disabled == False and user.type == CERT_CLIENT:
        logger.LogEntry(message='Enabled user "%s".' % user.name)

    send_key_email = flask.request.json.get('send_key_email')
    if send_key_email and user.email:
        try:
            user.send_key_email(flask.request.url_root[:-1])
        except EmailNotConfiguredError:
            return utils.jsonify({
                'error': EMAIL_NOT_CONFIGURED,
                'error_msg': EMAIL_NOT_CONFIGURED_MSG,
            }, 400)
        except EmailFromInvalid:
            return utils.jsonify({
                'error': EMAIL_FROM_INVALID,
                'error_msg': EMAIL_FROM_INVALID_MSG,
            }, 400)
        except EmailAuthInvalid:
            return utils.jsonify({
                'error': EMAIL_AUTH_INVALID,
                'error_msg': EMAIL_AUTH_INVALID_MSG,
            }, 400)

    return utils.jsonify(user.dict())

@app.app.route('/user/<org_id>/<user_id>', methods=['DELETE'])
@auth.session_auth
def user_delete(org_id, user_id):
    org = organization.get_by_id(org_id)
    user = org.get_user(user_id)
    name = user.name
    user.remove()

    event.Event(type=ORGS_UPDATED)
    event.Event(type=USERS_UPDATED, resource_id=org.id)

    user.disconnect()

    logger.LogEntry(message='Deleted user "%s".' % name)

    return utils.jsonify({})

@app.app.route('/user/<org_id>/<user_id>/otp_secret', methods=['PUT'])
@auth.session_auth
def user_otp_secret_put(org_id, user_id):
    org = organization.get_by_id(org_id)
    user = org.get_user(user_id)
    user.generate_otp_secret()
    user.commit()
    event.Event(type=USERS_UPDATED, resource_id=org.id)
    return utils.jsonify(user.dict())
