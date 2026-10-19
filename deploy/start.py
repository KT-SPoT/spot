"""Read the service-specific mounted secret without printing it."""
import os
import sys
from dotenv import load_dotenv

load_dotenv('/run/secrets/service_env', override=False, encoding='utf-8-sig')
service = os.environ.get('SPOT_SERVICE')
if service not in ('api', 'web'):
    raise SystemExit('SPOT_SERVICE must be api or web')
# Read owner-only Compose secret mounts as root, then run both services unprivileged.
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', f'src.{service}.app:create_app',
    '--factory', '--host', '0.0.0.0', '--port', '8765' if service == 'api' else '8768',
    '--workers', '1', '--no-access-log', '--no-proxy-headers'])
