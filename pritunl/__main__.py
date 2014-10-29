import pritunl

import optparse
import sys
import os

USAGE = """Usage: pritunl [command] [options]

Commands:
  start                 Start server
  version               Print the version and exit
  reset-password        Reset administrator password
"""

def pritunl_daemon(default_conf=None):
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option('-d', '--daemon', action='store_true',
        help='Daemonize process')
    parser.add_option('-p', '--pidfile', type='string',
        help='Path to create pid file')
    parser.add_option('-c', '--conf', type='string',
        help='Path to configuration file')
    (options, args) = parser.parse_args()

    if args:
        cmd = args[0]
    else:
        cmd = 'start'

    pritunl.set_conf_path(options.conf or default_conf)

    if cmd == 'version':
        print '%s v%s' % (pritunl.__title__, pritunl.__version__)
        sys.exit(0)

    if cmd == 'reset-password':
        from pritunl.constants import DEFAULT_USERNAME, DEFAULT_PASSWORD
        from pritunl import setup
        from pritunl import mongo
        setup.setup_db()
        collection = mongo.get_collection('administrators')
        collection.remove({})
        print 'Administrator password successfully reset:\n' + \
            '  username: "%s"\n  password: "%s"' % (
                DEFAULT_USERNAME, DEFAULT_PASSWORD)
        sys.exit(0)

    if cmd != 'start':
        raise ValueError('Invalid command')

    if options.daemon:
        pid = os.fork()
        if pid > 0:
            if options.pidfile:
                with open(options.pidfile, 'w') as pid_file:
                    pid_file.write('%s' % pid)
            sys.exit(0)
    else:
        print '##############################################################'
        print '#                                                            #'
        print '#                      /$$   /$$                         /$$ #'
        print '#                     |__/  | $$                        | $$ #'
        print '#   /$$$$$$   /$$$$$$  /$$ /$$$$$$   /$$   /$$ /$$$$$$$ | $$ #'
        print '#  /$$__  $$ /$$__  $$| $$|_  $$_/  | $$  | $$| $$__  $$| $$ #'
        print '# | $$  \ $$| $$  \__/| $$  | $$    | $$  | $$| $$  \ $$| $$ #'
        print '# | $$  | $$| $$      | $$  | $$ /$$| $$  | $$| $$  | $$| $$ #'
        print '# | $$$$$$$/| $$      | $$  |  $$$$/|  $$$$$$/| $$  | $$| $$ #'
        print '# | $$____/ |__/      |__/   \___/   \______/ |__/  |__/|__/ #'
        print '# | $$                                                       #'
        print '# | $$                                                       #'
        print '# |__/                                                       #'
        print '#                                                            #'
        print '##############################################################'

    pritunl.init_server()
