from pritunl.queues.init_user import QueueInitUser

from pritunl.constants import *
from pritunl import organization
from pritunl import queue
from pritunl import user

@queue.add_queue
class QueueInitUserPooled(QueueInitUser):
    type = 'init_user_pooled'

    def __init__(self, **kwargs):
        QueueInitUser.__init__(self, **kwargs)

        org_id = self.org_doc['_id']
        user_type = str(self.user_doc['type'])

        self.reserve_id = str(org_id) + '-' + {
            CERT_SERVER_POOL: CERT_SERVER,
            CERT_CLIENT_POOL: CERT_CLIENT,
        }[user_type]

    def task(self):
        self.user.initialize()
        self.load()

        if self.reserve_data:
            for field, value in self.reserve_data.items():
                setattr(self.user, field, value)
        self.user.commit()

    def pause_task(self):
        if self.reserve_data:
            return False
        self.load()
        if self.reserve_data:
            return False

        self.org.queue_com.running.clear()
        self.org.queue_com.popen_kill_all()

        return True

    def resume_task(self):
        self.org.queue_com.running.set()

@queue.add_reserve('queued_user')
def reserve_queued_user(org, name=None, email=None, type=None,
        disabled=None, resource_id=None, block=False):
    reserve_id = str(org.id) + '-' + type
    reserve_data = {}

    if name is not None:
        reserve_data['name'] = name
    if email is not None:
        reserve_data['email'] = email
    if type is not None:
        reserve_data['type'] = type
    if disabled is not None:
        reserve_data['disabled'] = disabled
    if resource_id is not None:
        reserve_data['resource_id'] = resource_id

    doc = QueueInitUserPooled.reserve(reserve_id, reserve_data, block=block)
    if not doc:
        return

    user_doc = doc['user_doc']
    user_doc.update(reserve_data)

    org = organization.Organization(doc=doc['org_doc'])
    return user.User(org=org, doc=user_doc)
