#!/usr/bin/env python3
"""Voice the atlas narration with ElevenLabs text-to-speech.

  python3 tts_gen.py --out AUDIO_DIR [--narration narration.json] [ids ...]

Reads {id: text} from narration.json and writes AUDIO_DIR/<id>.mp3, skipping files that exist.
The API key comes from the macOS Keychain (service from --keychain-service, account $USER) or from
$ELEVENLABS_API_KEY. Voice and model are parameters; defaults reproduce the published atlas.
"""
import argparse, json, os, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))


def api_key(service):
    k = os.environ.get('ELEVENLABS_API_KEY', '')
    if k:
        return k
    p = subprocess.run(['security', 'find-generic-password', '-a', os.environ.get('USER', ''), '-s', service, '-w'],
                       capture_output=True, text=True)
    return p.stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ids', nargs='*', help='only these clip ids (default: all)')
    ap.add_argument('--narration', default=os.path.join(HERE, 'narration.json'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--voice', default='3EuKHIEZbSzrHGNmdYsx')
    ap.add_argument('--model', default='eleven_v4')
    ap.add_argument('--stability', type=float, default=0.0)
    ap.add_argument('--similarity', type=float, default=0.85)
    ap.add_argument('--seed', type=int, default=4242)
    ap.add_argument('--keychain-service', default='elevenlabs')
    ap.add_argument('--force', action='store_true', help='re-generate clips that already exist')
    ap.add_argument('--dry-run', action='store_true', help='print ids and the character total only')
    a = ap.parse_args(argv)
    d = json.load(open(a.narration, encoding='utf-8'))
    items = [(k, v) for k, v in d.items() if not a.ids or k in a.ids]
    missing = sorted(set(a.ids) - set(d))
    if missing:
        raise SystemExit('unknown ids: %s' % ', '.join(missing))
    os.makedirs(a.out, exist_ok=True)
    todo = [(k, v) for k, v in items if a.force or not (os.path.exists(os.path.join(a.out, k + '.mp3'))
                                                         and os.path.getsize(os.path.join(a.out, k + '.mp3')) > 1000)]
    print('clips to voice: %d, characters: %d' % (len(todo), sum(len(v) for _, v in todo)))
    if a.dry_run or not todo:
        return 0
    key = api_key(a.keychain_service)
    if not key:
        raise SystemExit('no ElevenLabs key: set ELEVENLABS_API_KEY or add it to the Keychain')

    def gen(item):
        k, text = item
        path = os.path.join(a.out, k + '.mp3')
        body = json.dumps({'text': text, 'model_id': a.model,
                           'voice_settings': {'stability': a.stability, 'similarity_boost': a.similarity},
                           'seed': a.seed, 'apply_text_normalization': 'on', 'language_code': 'ru'}).encode()
        last = ''
        for attempt in range(4):
            req = urllib.request.Request(
                'https://api.elevenlabs.io/v1/text-to-speech/%s?output_format=mp3_44100_64' % a.voice, data=body,
                headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                open(path, 'wb').write(data)
                return k, 'ok %d' % len(data)
            except urllib.error.HTTPError as e:
                last = 'HTTP %d %s' % (e.code, e.read()[:200].decode('utf-8', 'replace'))
                if e.code in (429, 500, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                return k, last
            except Exception as e:  # network hiccup
                last = str(e)
                time.sleep(3)
        return k, 'failed: ' + last

    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(gen, todo))
    bad = [r for r in res if not r[1].startswith('ok')]
    print('done %d, failed %d' % (len(res), len(bad)))
    for k, why in bad:
        print(k, why)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
