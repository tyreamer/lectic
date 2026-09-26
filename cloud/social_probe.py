"""Run from the actual hosting service, with consented representative public links.

This intentionally performs no model calls. A URL list is operator input, not a web API.
"""
import argparse
import hashlib
import json
import platform as os_platform
import time
from pathlib import Path
from .config import Settings, VERSION
from .retrieval import retrieve, platform, NeedsContent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('links',type=Path,help='JSON list of {url, expected_type, expected_items}')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--environment',required=True,help='Label the actual environment; local results are not hosting evidence')
    args=parser.parse_args(); settings=Settings()
    results=[]
    for sample in json.loads(args.links.read_text()):
        started=time.monotonic()
        row={'url_hash':hashlib.sha256(sample['url'].encode()).hexdigest(),'expected_type':sample['expected_type'],
             'expected_items':sample['expected_items'],'platform':platform(sample['url'])}
        try:
            items=retrieve(sample['url'],settings)
            row.update(state='retrieved',items=len(items),bytes=sum(len(i['raw']) for i in items),
                       complete_count=len(items)==sample['expected_items'])
        except Exception as exc: row.update(state='needs_content',error_type=type(exc).__name__,complete_count=False)
        row['seconds']=round(time.monotonic()-started,2);results.append(row)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'environment':args.environment,'os':os_platform.system(),'processing_version':VERSION,
         'measured_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'samples':results,
         'limits':'Retrieved count is not proof of source completeness. Inspect every original and compare phone-supplied payloads.'},indent=2))


if __name__=='__main__':main()
