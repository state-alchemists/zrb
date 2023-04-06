from zrb.helper.docker_compose.fetch_external_env import fetch_external_env


def test_fetch_external_env():
    data = {
        'services': {
            'service_1': {
                'environment': [
                    'PORT=${PORT_A:-8080}',
                    'URL=${PROTOCOL_A:-http}://${HOST_A1:-${HOST_A2:-${HOST_A3:-localhost}}}${URL_A}', # noqa
                    'SECRET=${SECRET_A}',
                    'LITERAL=LITERAL',
                ]
            },
            'service_2': {
                'environment': {
                    'PORT': '${PORT_B:-8080}',
                    'URL': '${PROTOCOL_B:-http}://${HOST_B1:-${HOST_B2:-${HOST_B3:-localhost}}}${URL_B}', # noqa
                    'SECRET': '${SECRET_A}',
                    'LITERAL': 'LITERAL',
                }
            }
        }
    }
    external_env = fetch_external_env(data)
    assert external_env.get('PORT_A') == '8080'
    assert external_env.get('PROTOCOL_A') == 'http'
    assert external_env.get('HOST_A1') == ''
    assert external_env.get('HOST_A2') == ''
    assert external_env.get('HOST_A3') == 'localhost'
    assert external_env.get('URL_A') == ''
    assert external_env.get('PORT_B') == '8080'
    assert external_env.get('PROTOCOL_B') == 'http'
    assert external_env.get('HOST_B1') == ''
    assert external_env.get('HOST_B2') == ''
    assert external_env.get('HOST_B3') == 'localhost'
    assert external_env.get('URL_B') == ''