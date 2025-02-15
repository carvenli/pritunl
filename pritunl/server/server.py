from pritunl.server.output import ServerOutput
from pritunl.server.output_link import ServerOutputLink
from pritunl.server.bandwidth import ServerBandwidth
from pritunl.server.ip_pool import ServerIpPool
from pritunl.server.instance import ServerInstance

from pritunl.constants import *
from pritunl.exceptions import *
from pritunl.helpers import *
from pritunl import settings
from pritunl import logger
from pritunl import host
from pritunl import utils
from pritunl import mongo
from pritunl import queue
from pritunl import transaction
from pritunl import event
from pritunl import messenger
from pritunl import organization

import os
import subprocess
import threading
import random
import collections

_resource_lock = collections.defaultdict(threading.Lock)

dict_fields = [
    'id',
    'name',
    'status',
    'start_timestamp',
    'uptime',
    'instances',
    'organizations',
    'network',
    'network_mode',
    'network_start',
    'network_end',
    'bind_address',
    'port',
    'protocol',
    'dh_param_bits',
    'dh_params',
    'mode',
    'multi_device',
    'local_networks',
    'dns_servers',
    'search_domain',
    'otp_auth',
    'cipher',
    'jumbo_frames',
    'lzo_compression',
    'inter_client',
    'ping_interval',
    'ping_timeout',
    'max_clients',
    'replica_count',
    'debug',
]

class Server(mongo.MongoObject):
    fields = {
        'name',
        'network',
        'network_lock',
        'bind_address',
        'port',
        'protocol',
        'dh_param_bits',
        'mode',
        'network_mode',
        'network_start',
        'network_end',
        'multi_device',
        'local_networks',
        'dns_servers',
        'search_domain',
        'otp_auth',
        'tls_auth',
        'tls_auth_key',
        'lzo_compression',
        'inter_client',
        'ping_interval',
        'ping_timeout',
        'debug',
        'cipher',
        'jumbo_frames',
        'organizations',
        'hosts',
        'links',
        'primary_organization',
        'primary_user',
        'ca_certificate',
        'dh_params',
        'status',
        'start_timestamp',
        'max_clients',
        'replica_count',
        'instances',
        'instances_count',
    }
    fields_default = {
        'network_mode': TUNNEL,
        'multi_device': False,
        'dns_servers': [],
        'otp_auth': False,
        'tls_auth': True,
        'lzo_compression': False,
        'inter_client': True,
        'ping_interval': 10,
        'ping_timeout': 60,
        'debug': False,
        'cipher': 'aes256',
        'jumbo_frames': False,
        'organizations': [],
        'hosts': [],
        'links': [],
        'status': OFFLINE,
        'max_clients': 2048,
        'replica_count': 1,
        'instances': [],
        'instances_count': 0,
    }
    cache_prefix = 'server'

    def __init__(self, name=None, network=None, network_mode=None,
            network_start=None, network_end=None, bind_address=None,
            port=None, protocol=None, dh_param_bits=None,
            mode=None, multi_device=None, local_networks=None,
            dns_servers=None, search_domain=None, otp_auth=None, cipher=None,
            jumbo_frames=None, lzo_compression=None, inter_client=None,
            ping_interval=None, ping_timeout=None, max_clients=None,
            replica_count=None, debug=None, **kwargs):
        mongo.MongoObject.__init__(self, **kwargs)

        if 'network' in self.loaded_fields:
            self._orig_network = self.network
        self._orgs_added = []
        self._orgs_removed = []

        if name is not None:
            self.name = name
        if network is not None:
            self.network = network
        if network_mode is not None:
            self.network_mode = network_mode
        if network_start is not None:
            self.network_start = network_start
        if network_end is not None:
            self.network_end = network_end
        if bind_address is not None:
            self.bind_address = bind_address
        if port is not None:
            self.port = port
        if protocol is not None:
            self.protocol = protocol
        if dh_param_bits is not None:
            self.dh_param_bits = dh_param_bits
        if mode is not None:
            self.mode = mode
        if multi_device is not None:
            self.multi_device = multi_device
        if local_networks is not None:
            self.local_networks = local_networks
        if dns_servers is not None:
            self.dns_servers = dns_servers
        if search_domain is not None:
            self.search_domain = search_domain
        if otp_auth is not None:
            self.otp_auth = otp_auth
        if cipher is not None:
            self.cipher = cipher
        if jumbo_frames is not None:
            self.jumbo_frames = jumbo_frames
        if lzo_compression is not None:
            self.lzo_compression = lzo_compression
        if inter_client is not None:
            self.inter_client = inter_client
        if ping_interval is not None:
            self.ping_interval = ping_interval
        if ping_timeout is not None:
            self.ping_timeout = ping_timeout
        if max_clients is not None:
            self.max_clients = max_clients
        if replica_count is not None:
            self.replica_count = replica_count
        if debug is not None:
            self.debug = debug

    @cached_static_property
    def collection(cls):
        return mongo.get_collection('servers')

    @cached_static_property
    def user_collection(cls):
        return mongo.get_collection('users')

    @cached_static_property
    def clients_collection(cls):
        return mongo.get_collection('clients')

    @cached_static_property
    def org_collection(cls):
        return mongo.get_collection('organizations')

    @cached_static_property
    def host_collection(cls):
        return mongo.get_collection('hosts')

    def dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'status': PENDING if not self.dh_params else self.status,
            'uptime': self.uptime,
            'users_online': self.users_online,
            'devices_online': self.devices_online,
            'user_count': self.user_count,
            'network': self.network,
            'bind_address': self.bind_address,
            'port': self.port,
            'protocol': self.protocol,
            'dh_param_bits': self.dh_param_bits,
            'mode': self.mode,
            'network_mode': self.network_mode,
            'network_start': self.network_start,
            'network_end': self.network_end,
            'multi_device': self.multi_device,
            'local_networks': self.local_networks,
            'dns_servers': self.dns_servers,
            'search_domain': self.search_domain,
            'otp_auth': True if self.otp_auth else False,
            'cipher': self.cipher,
            'jumbo_frames': self.jumbo_frames,
            'lzo_compression': self.lzo_compression,
            'inter_client': True if self.inter_client else False,
            'ping_interval': self.ping_interval,
            'ping_timeout': self.ping_timeout,
            'max_clients': self.max_clients,
            'replica_count': self.replica_count,
            'debug': True if self.debug else False,
        }

    @property
    def uptime(self):
        if self.status != ONLINE or not self.start_timestamp:
            return
        return max((utils.now() - self.start_timestamp).seconds, 1)

    @cached_property
    def users_online(self):
        return len(self.clients_collection.distinct("user_id", {
            'server_id': self.id,
            'type': CERT_CLIENT,
        }))

    @cached_property
    def devices_online(self):
        return self.clients_collection.find({
            'server_id': self.id,
            'type': CERT_CLIENT,
        }).count()

    @cached_property
    def user_count(self):
        return organization.get_user_count_multi(org_ids=self.organizations)

    @cached_property
    def bandwidth(self):
        return ServerBandwidth(self.id)

    @cached_property
    def ip_pool(self):
        return ServerIpPool(self)

    @cached_property
    def output(self):
        return ServerOutput(self.id)

    @cached_property
    def output_link(self):
        return ServerOutputLink(self.id)

    def initialize(self):
        self.generate_tls_auth_start()
        try:
            self.generate_dh_param()
        finally:
            self.generate_tls_auth_wait()

    def queue_dh_params(self, block=False):
        queue.start('dh_params', block=block, server_id=self.id,
            dh_param_bits=self.dh_param_bits, priority=HIGH)
        self.dh_params = None

        if block:
            self.load()

    def get_cache_key(self, suffix=None):
        if not self.cache_prefix:
            raise AttributeError('Cached config object requires cache_prefix')
        key = self.cache_prefix + '-' + self.id
        if suffix:
            key += '-%s' % suffix
        return key

    def get_ip_addr(self, org_id, user_id):
        return self.ip_pool.get_ip_addr(org_id, user_id)

    def assign_ip_addr(self, org_id, user_id):
        if not self.network_lock:
            self.ip_pool.assign_ip_addr(org_id, user_id)
        else:
            queue.start('assign_ip_addr', server_id=self.id, org_id=org_id,
                user_id=user_id)

    def unassign_ip_addr(self, org_id, user_id):
        if not self.network_lock:
            self.ip_pool.unassign_ip_addr(org_id, user_id)
        else:
            queue.start('unassign_ip_addr', server_id=self.id, org_id=org_id,
                user_id=user_id)

    def get_sync_remotes(self):
        remotes = []
        spec = {
            '_id': {'$in': self.hosts},
        }
        project = {
            '_id': False,
            'public_address': True,
            'auto_public_address': True,
        }

        for doc in self.host_collection.find(spec, project):
            address = doc['public_address'] or doc['auto_public_address']
            remotes.append('%s://%s:%s' % (
                'https' if settings.conf.ssl else 'http',
                address,
                settings.conf.port,
            ))

        return remotes

    def get_key_remotes(self, include_link_addr=False):
        remotes = []
        spec = {
            '_id': {'$in': self.hosts},
        }
        project = {
            '_id': False,
            'public_address': True,
            'auto_public_address': True,
        }

        if include_link_addr:
            project['link_address'] = True

        for doc in self.host_collection.find(spec, project):
            if include_link_addr and doc['link_address']:
                address = doc['link_address']
            else:
                address = doc['public_address'] or doc['auto_public_address']
            remotes.append('remote %s %s' % (address, self.port))

        random.shuffle(remotes)

        if len(remotes) > 1:
            remotes.append('remote-random')

        return '\n'.join(remotes)

    def commit(self, *args, **kwargs):
        tran = None

        if 'network' in self.loaded_fields and \
                self.network != self._orig_network:
            tran = transaction.Transaction()
            if self.network_lock:
                raise ServerNetworkLocked('Server network is locked', {
                    'server_id': self.id,
                    'lock_id': self.network_lock,
                })
            else:
                queue_ip_pool = queue.start('assign_ip_pool',
                    transaction=tran,
                    server_id=self.id,
                    network=self.network,
                    old_network=self._orig_network,
                )
                self.network_lock = queue_ip_pool.id

        for org_id in self._orgs_added:
            self.ip_pool.assign_ip_pool_org(org_id)

        for org_id in self._orgs_removed:
            self.ip_pool.unassign_ip_pool_org(org_id)

        mongo.MongoObject.commit(self, transaction=tran, *args, **kwargs)

        if tran:
            messenger.publish('queue', 'queue_updated',
                transaction=tran)
            tran.commit()

    def remove(self):
        queue.stop(spec={
            'type': 'dh_params',
            'server_id': self.id,
        })
        self.remove_primary_user()
        mongo.MongoObject.remove(self)

    def iter_links(self, fields=None):
        from pritunl.server.utils import iter_servers

        spec = {
            '_id': {'$in': [x['server_id'] for x in self.links]},
        }
        for svr in iter_servers(spec=spec, fields=fields):
            yield svr

    def create_primary_user(self):
        logger.debug('Creating primary user', 'server',
            server_id=self.id,
        )

        try:
            org = self.iter_orgs().next()
        except StopIteration:
            self.stop()
            raise ServerMissingOrg('Primary user cannot be created ' + \
                'without any organizations', {
                    'server_id': self.id,
                })

        user = org.new_user(name=SERVER_USER_PREFIX + str(self.id),
            type=CERT_SERVER, resource_id=self.id)

        self.primary_organization = org.id
        self.primary_user = user.id
        self.commit(('primary_organization', 'primary_user'))

    def remove_primary_user(self):
        logger.debug('Removing primary user', 'server',
            server_id=self.id,
        )

        self.user_collection.remove({
            'resource_id': self.id,
        })

        self.primary_organization = None
        self.primary_user = None

    def add_org(self, org_id):
        if not isinstance(org_id, basestring):
            org_id = org_id.id

        logger.debug('Adding organization to server', 'server',
            server_id=self.id,
            org_id=org_id,
        )

        if org_id in self.organizations:
            logger.debug('Organization already on server, skipping', 'server',
                server_id=self.id,
                org_id=org_id,
            )
            return

        self.organizations.append(org_id)
        self.changed.add('organizations')
        self.generate_ca_cert()
        self._orgs_added.append(org_id)

    def remove_org(self, org_id):
        if not isinstance(org_id, basestring):
            org_id = org_id.id

        if org_id not in self.organizations:
            return

        logger.debug('Removing organization from server', 'server',
            server_id=self.id,
            org_id=org_id,
        )

        if self.primary_organization == org_id:
            self.remove_primary_user()

        try:
            self.organizations.remove(org_id)
        except ValueError:
            pass

        self.changed.add('organizations')
        self.generate_ca_cert()
        self._orgs_removed.append(org_id)

    def iter_orgs(self, fields=None):
        spec = {
            '_id': {'$in': self.organizations},
        }
        for org in organization.iter_orgs(spec=spec, fields=fields):
            yield org

    def get_org(self, org_id, fields=None):
        if org_id in self.organizations:
            return organization.get_by_id(org_id, fields=fields)

    def get_org_fields(self, fields=None):
        project = {}
        push = {}

        for field in fields:
            if field == 'id':
                project['_id'] = True
                push[field] = '$_id'
            else:
                project[field] = True
                push[field] = '$' + field

        response = self.org_collection.aggregate([
            {'$match': {
                '_id': {'$in': self.organizations},
            }},
            {'$project': project},
            {'$group': {
                '_id': None,
                'orgs': {'$push': push},
            }},
        ])

        val = None
        for val in response:
            break

        if val:
            docs = val['orgs']
        else:
            docs = []

        return docs

    def add_host(self, host_id):
        logger.debug('Adding host to server', 'server',
            server_id=self.id,
            host_id=host_id,
        )

        if host_id in self.hosts:
            logger.debug('Host already on server, skipping', 'server',
                server_id=self.id,
                host_id=host_id,
            )
            return

        if self.links:
            hosts_set = set(self.hosts)
            hosts_set.add(host_id)

            spec = {
            '_id': {'$in': [x['server_id'] for x in self.links]},
            }
            project = {
                '_id': True,
                'hosts': True,
            }

            for doc in self.collection.find(spec, project):
                if hosts_set & set(doc['hosts']):
                    raise ServerLinkCommonHostError(
                        'Servers have a common host')

        self.hosts.append(host_id)
        self.changed.add('hosts')

    def remove_host(self, host_id):
        if host_id not in self.hosts:
            logger.warning('Attempted to remove host that does not exists',
                'server',
                server_id=self.id,
                host_id=host_id,
            )
            return

        logger.debug('Removing host from server', 'server',
            server_id=self.id,
            host_id=host_id,
        )

        self.hosts.remove(host_id)

        response = self.collection.update({
            '_id': self.id,
            'instances.host_id': host_id,
        }, {
            '$pull': {
                'hosts': host_id,
                'instances': {
                    'host_id': host_id,
                },
            },
            '$inc': {
                'instances_count': -1,
            },
        })

        if response['updatedExisting']:
            self.publish('start', extra={
                'prefered_hosts': host.get_prefered_hosts(
                    self.hosts, self.replica_count),
            })

        doc = self.collection.find_and_modify({
            '_id': self.id,
        }, {
            '$pull': {
                'hosts': host_id,
            },
        }, {
            'hosts': True,
        }, new=True)

        if doc and not doc['hosts']:
            self.status = OFFLINE
            self.commit('status')

    def iter_hosts(self, fields=None):
        spec = {
            '_id': {'$in': self.hosts}
        }
        for hst in host.iter_hosts(spec=spec, fields=fields):
            yield hst

    def get_by_id(self, host_id):
        if host_id in self.hosts:
            return host.get_by_id(host_id)

    def generate_dh_param(self):
        doc = queue.find({
            'type': 'dh_params',
            'server_id': self.id,
        })
        if doc:
            if doc['dh_param_bits'] != self.dh_param_bits:
                queue.stop(doc['_id'])
            else:
                return

        reserved = queue.reserve('pooled_dh_params', svr=self)
        if not reserved:
            reserved = queue.reserve('queued_dh_params', svr=self)

        if reserved:
            queue.start('dh_params', dh_param_bits=self.dh_param_bits,
                priority=LOW)
            return

        self.queue_dh_params()

    def generate_tls_auth_start(self):
        self.tls_auth_temp_path = utils.get_temp_path()
        self.tls_auth_path = os.path.join(
            self.tls_auth_temp_path, TLS_AUTH_NAME)

        os.makedirs(self.tls_auth_temp_path)
        args = [
            'openvpn', '--genkey',
            '--secret', self.tls_auth_path,
        ]
        try:
            self.tls_auth_process = subprocess.Popen(args,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except:
            utils.rmtree(self.tls_auth_temp_path)
            raise

    def generate_tls_auth_wait(self):
        try:
            return_code = self.tls_auth_process.wait()
            if return_code:
                raise ValueError('Popen returned ' +
                    'error exit code %r' % return_code)
            self.read_file('tls_auth_key', self.tls_auth_path)
        finally:
            utils.rmtree(self.tls_auth_temp_path)

    def generate_tls_auth(self):
        self.generate_tls_auth_start()
        self.generate_tls_auth_wait()

    def generate_ca_cert(self):
        ca_certificate = ''
        for org in self.iter_orgs():
            ca_certificate += utils.get_cert_block(org.ca_certificate) + '\n'
        self.ca_certificate = ca_certificate.rstrip('\n')

    def get_cursor_id(self):
        return messenger.get_cursor_id('servers')

    def publish(self, message, transaction=None, extra=None):
        extra = extra or {}
        extra.update({
            'server_id': self.id,
        })
        messenger.publish('servers', message,
            extra=extra, transaction=transaction)

    def subscribe(self, cursor_id=None, timeout=None):
        for msg in messenger.subscribe('servers', cursor_id=cursor_id,
                timeout=timeout):
            if msg.get('server_id') == self.id:
                yield msg

    def send_link_events(self):
        event.Event(type=SERVER_LINKS_UPDATED, resource_id=self.id)
        for link in self.links:
            event.Event(type=SERVER_LINKS_UPDATED,
                resource_id=link['server_id'])

    def pre_start_check(self):
        if not self.tls_auth_key:
            self.generate_tls_auth()
            self.commit('tls_auth_key')

        if not self.ca_certificate:
            self.generate_ca_cert()
            self.commit('ca_certificate')

    def run(self, send_events=False):
        self.pre_start_check()
        instance = ServerInstance(self)
        instance.run(send_events=send_events)

    def start(self, timeout=None):
        timeout = timeout or settings.vpn.op_timeout
        cursor_id = self.get_cursor_id()

        if self.status != OFFLINE:
            return

        if not self.dh_params:
            self.generate_dh_param()
            return

        if not self.organizations:
            raise ServerMissingOrg('Server cannot be started ' + \
                'without any organizations', {
                    'server_id': self.id,
                })

        self.pre_start_check()

        start_timestamp = utils.now()
        response = self.collection.update({
            '_id': self.id,
            'status': OFFLINE,
            'instances_count': 0,
        }, {'$set': {
            'status': ONLINE,
            'start_timestamp': start_timestamp,
        }})

        if not response['updatedExisting']:
            raise ServerInstanceSet('Server instances already running. %r', {
                    'server_id': self.id,
                })
        self.status = ONLINE
        self.start_timestamp = start_timestamp

        replica_count = min(self.replica_count, len(self.hosts))

        started_count = 0
        error_count = 0
        try:
            self.publish('start', extra={
                'prefered_hosts': host.get_prefered_hosts(
                    self.hosts, replica_count),
            })

            for x_timeout in (4, timeout):
                for msg in self.subscribe(cursor_id=cursor_id,
                        timeout=x_timeout):
                    message = msg['message']
                    if message == 'started':
                        started_count += 1
                        if started_count + error_count >= replica_count:
                            break
                    elif message == 'error':
                        error_count += 1
                        if started_count + error_count >= replica_count:
                            break

                if started_count:
                    break

            if not started_count:
                if error_count:
                    raise ServerStartError('Server failed to start', {
                        'server_id': self.id,
                    })
                else:
                    raise ServerStartError('Server start timed out', {
                        'server_id': self.id,
                    })
        except:
            self.publish('force_stop')
            self.collection.update({
                '_id': self.id,
            }, {'$set': {
                'status': OFFLINE,
                'instances': [],
                'instances_count': 0,
            }})
            self.status = OFFLINE
            self.instances = []
            self.instances_count = 0
            raise

    def stop(self, force=False):
        logger.debug('Stopping server', 'server',
            server_id=self.id,
        )

        if self.status != ONLINE:
            return

        response = self.collection.update({
            '_id': self.id,
            'status': ONLINE,
        }, {'$set': {
            'status': OFFLINE,
            'start_timestamp': None,
            'instances': [],
            'instances_count': 0,
        }})

        if not response['updatedExisting']:
            raise ServerStopError('Server not running', {
                    'server_id': self.id,
                })
        self.status = OFFLINE

        if force:
            self.publish('force_stop')
        else:
            self.publish('stop')

    def force_stop(self):
        self.stop(force=True)

    def restart(self):
        if self.status != ONLINE:
            self.start()
            return
        logger.debug('Restarting server', 'server',
            server_id=self.id,
        )
        self.stop()
        self.start()
