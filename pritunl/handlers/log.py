from pritunl import utils
from pritunl import app
from pritunl import auth
from pritunl import logger

@app.app.route('/log', methods=['GET'])
@auth.session_auth
def log_get():
    log_entries = []

    for log_entry in logger.iter_log_entries():
        log_entries.append(log_entry.dict())

    return utils.jsonify(log_entries)
