from pritunl.settings.group_mongo import SettingsGroupMongo

class SettingsUser(SettingsGroupMongo):
    group = 'user'
    fields = {
        'otp_secret_len': 16,
        'cert_key_bits': 4096,
        'cert_message_digest': 'sha256',
        'otp_cache_ttl': 43200,
        'page_count': 10,
    }
