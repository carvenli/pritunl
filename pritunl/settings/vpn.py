from pritunl.settings.group_mongo import SettingsGroupMongo

class SettingsVpn(SettingsGroupMongo):
    group = 'vpn'
    fields = {
        'client_ttl': 300,
        'peer_limit': 300,
        'peer_limit_timeout': 10,
        'default_dh_param_bits': 1536,
        'cache_otp_codes': True,
        'log_lines': 5000,
        'server_ping': 3,
        'server_ping_ttl': 6,
        'status_update_rate': 3,
        'http_request_timeout': 10,
        'op_timeout': 10,
        'bandwidth_update_rate': 15,
        'safe_priv_subnets': [
            '10.0.0.0/8',
            '100.64.0.0/10',
            '172.16.0.0/12',
            '192.0.0.0/24',
            '192.168.0.0/16',
            '198.18.0.0/15',
            '50.203.0.0/16',
        ],
    }
