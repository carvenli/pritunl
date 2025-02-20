from pritunl.helpers import *
from pritunl import utils
from pritunl import logger

import threading

@interrupter
def _time_sync_thread():
    while True:
        try:
            utils.sync_time()
        except:
            logger.exception('Failed to sync time with mongo server',
                'runners')
        yield interrupter_sleep(15)

def start_time_sync():
    threading.Thread(target=_time_sync_thread).start()
