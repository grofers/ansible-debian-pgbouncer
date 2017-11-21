from collections import defaultdict

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor
import collectd
import psycopg2

# Default host, override in config by specifying 'Host'
HOST = 'localhost'

# Default port, override in config by specifying 'Port'
PORT = 5432

# Default database, override in config by specifying 'Database'
DBNAME = 'pgbouncer'

# Default user, override in config by specifying 'User'
USER = 'postgres'

# Default password, override in config by specifying 'Password'
PASSWORD = ''


def get_stats():
    conn, cur = None, None
    stats = {}
    try:
        conn = psycopg2.connect(
            database=DBNAME,
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        stats = _get_stats(cur)
    finally:
        if cur is not None:
            cur.close()
            if conn is not None:
                conn.close()

    return stats


def _get_stats(cur):
    stats = defaultdict(dict)

    cur.execute('SHOW STATS;')
    for data in cur.fetchall():
        key = data.pop('database', None)
        # all metrics needed from this query
        stats[key] = data

    cur.execute('SHOW POOLS;')
    for data in cur.fetchall():
        key = data.pop('database', None)

        # pop the metrics not needed from this query
        data.pop('pool_mode', None)
        data.pop('user', None)
        stats[key].update(data)

    cur.execute('SHOW DATABASES')
    for data in cur.fetchall():
        key = data.pop('database', None)

        # filtering the metrics needed from this query
        values = {
            'pool_size': data['pool_size'],
            'reserve_pool': data['reserve_pool'],
            'max_connections': data['max_connections'],
            'current_connections': data['current_connections']
        }
        stats[key].update(values)

    return stats


def read_callback(data=None):
    stats = get_stats()
    if not stats:
        collectd.error('pgbouncer plugin: No info received')
        return

    for database, metrics in stats.iteritems():
        for metric, value in metrics.iteritems():
            val = collectd.Values(
                plugin='pgbouncer_info',
                plugin_instance=database
            )
            val.type = 'gauge'
            val.type_instance = metric
            val.values = [value]
            val.dispatch()


def configure_callback(config):
    global HOST, PORT, DBNAME, USER, PASSWORD
    for option in config.children:
        if option.key == 'Host':
            HOST = option.values[0]
        elif option.key == 'Port':
            PORT = int(option.values[0])
        elif option.key == 'Database':
            DBNAME = option.values[0]
        elif option.key == 'User':
            USER = option.values[0]
        elif option.key == 'Password':
            PASSWORD = option.values[0]
        else:
            collectd.warning(
                'pgbouncer_info plugin: Unknown config key: %s.', option.key
            )


# register callbacks
collectd.register_read(read_callback)
collectd.register_config(configure_callback)
