"""Check EC2 -> GPU connectivity without importing torch or changing servers."""
import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def check(base_url, token, *, generate=False, expected_sha=None):
    if not base_url or not token:
        raise ValueError('COMMON_LLM_URL and THINKING_LLM_TOKEN are required')
    base_url = base_url.rstrip('/')
    def request(route, payload=None):
        req = urllib.request.Request(base_url + route,
            data=None if payload is None else json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'X-LLM-Token': token})
        with urllib.request.urlopen(req, timeout=180 if payload else 10) as response:
            return json.load(response)
    health = request('/health')
    result = {'reachable': health.get('status') == 'ok', 'loaded': health.get('loaded'),
              'structured_mode': health.get('structured_mode'),
              'loaded_identity': health.get('loaded_identity'), 'generation_checked': False}
    if not result['reachable']:
        raise ValueError('GPU API did not report healthy status')
    if generate:
        response = request('/draft', {'document_type': 'report', 'topic': 'Connection check',
            'facts': ['The reviewer checked 4 of 10 records.', 'The other 6 records were not checked.'],
            'target_chars': 150, 'tone': '기본'})
        if not isinstance(response.get('content'), str) or not response['content'].strip():
            raise ValueError('GPU returned an empty draft')
        identity = response.get('loaded_identity') or {}
        if identity.get('profile') != 'curated_over1000_20261119':
            raise ValueError('GPU is not using the selected Curated1459 writing profile')
        if expected_sha and identity.get('adapter_sha256') != expected_sha:
            raise ValueError('GPU adapter fingerprint differs from the requested model')
        result.update(generation_checked=True, loaded_identity=identity, loaded=True)
    elif expected_sha and (result['loaded_identity'] or {}).get('adapter_sha256') != expected_sha:
        raise ValueError('Use --generate to load and verify the requested adapter')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true', help='Also authenticate and generate one synthetic draft')
    parser.add_argument('--expected-adapter-sha256')
    args = parser.parse_args()
    load_dotenv(ROOT / 'backend/.env')
    try:
        result = check(os.getenv('COMMON_LLM_URL', '').strip(), os.getenv('THINKING_LLM_TOKEN', '').strip(),
                       generate=args.generate, expected_sha=args.expected_adapter_sha256)
    except (ValueError, OSError, urllib.error.URLError) as exc:
        # Do not print configured URLs, credentials or complete HTTP payloads.
        print(json.dumps({'ok': False, 'error': type(exc).__name__}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
