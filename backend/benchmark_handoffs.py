"""Offline synthetic fixture benchmark. No provider or application data access."""
import argparse
import json
from pathlib import Path
from studio.handoffs import byte_size, encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokenizer', help='Optional installed tiktoken encoding; never inferred.')
    args = parser.parse_args()
    fixture = json.loads((Path(__file__).parent/'tests/fixtures/handoff-v3.json').read_text(encoding='utf-8'))
    sizes = {key: byte_size(fixture[key]) for key in ('packet', 'bootstrap')}
    result = {'unit': 'minified UTF-8 bytes', **sizes, 'legacy_fixture_bytes': fixture['legacy_bytes'],
              'packet_reduction_percent': round(100*(1-sizes['packet']/fixture['legacy_bytes']), 2),
              'tokenizer': args.tokenizer, 'tokens': None}
    if args.tokenizer:
        import tiktoken
        tokenizer = tiktoken.get_encoding(args.tokenizer)
        result['tokens'] = {key: len(tokenizer.encode(encoded(fixture[key]).decode('utf-8'))) for key in sizes}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
