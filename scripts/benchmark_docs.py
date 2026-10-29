#!/usr/bin/env python3
"""Run curated retrieval cases against a registered installed corpus and XDOX index."""
import argparse
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
import platform
import time

from xdox_lookup import Lookup, sha


def verify_source(ref):
    path=Path(ref['file'])
    assert sha(path.read_bytes())==ref['sha256'], 'Source hash mismatch'
    lines=path.read_text().splitlines()
    assert 1<=ref['line_start']<=ref['line_end']<=len(lines), 'Invalid source range'
    if ref['anchor']:
        assert any(line.strip()=='.. _'+ref['anchor']+':' for line in lines[ref['line_start']-1:ref['line_end']]), 'Anchor not in cited source'


def assess(case,result):
    expected=case['expected']
    assert result['status']==expected['status'], ('status',result['status'])
    assert result['availability']==expected['availability'], ('availability',result['availability'])
    assert result['target']['project_type']==case['project_type']
    assert result['target']['platform']==case['platform']
    assert result['corpus']['id']==case['version']
    for row in result.get('results',[]):
        assert row['corpus_version']==result['corpus']['label']
        assert row['target']==result['target']
        verify_source(row['source'])
        ref=row['source']
        text='\n'.join(Path(ref['file']).read_text().splitlines()[ref['line_start']-1:ref['line_end']])
        assert row['text']==text[:6000], 'Returned text differs from cited source'
        for source in row['compatibility_sources']+[x['source'] for x in row['deprecation_notices']]:
            verify_source(source)
        if row.get('also_documented_on_parent'):
            verify_source(row['also_documented_on_parent']['source'])
        if row.get('index_hit'):
            assert row['index_hit']['docs_version']==result['corpus']['label']
    if expected.get('error_contains'):
        assert expected['error_contains'] in result.get('error','')
    row_checks=set(expected)-{'status','availability','error_contains'}
    if row_checks:
        matching=[]
        for row in result['results']:
            checks=[]
            for key in row_checks:
                value=expected[key]
                if key=='source_suffix': checks.append(row['source']['relative_file'].endswith(value))
                elif key=='anchor': checks.append(row['source']['anchor']==value)
                elif key=='parent': checks.append(row.get('also_documented_on_parent',{}).get('class_name')==value)
                elif key=='text_contains': checks.append(value.casefold() in row['text'].casefold())
                elif key=='notice_contains': checks.append(any(value in n['text'] for n in row['deprecation_notices']))
                else: checks.append(row.get(key)==value)
            if all(checks): matching.append(row)
        assert matching, 'Expected evidence not found in returned results'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--cases',type=Path,default=Path('benchmarks/documentation-cases.json'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not __debug__:
        parser.error("Run benchmark without -O; validation assertions must be enabled")
    args.output.mkdir(parents=True,exist_ok=False)
    cases=json.loads(args.cases.read_text())['cases']
    cache={}
    records=[]
    start=time.monotonic()
    for case in cases:
        at=time.monotonic()
        try:
            key=(case['version'],case['project_type'],case['platform'])
            if key not in cache:
                cache[key]=Lookup(args.registry,*key)
            service=cache[key]
            result=service.lookup(case['class_name'],case.get('member')) if case['operation']=='lookup' else service.search(case['query'],case.get('max_results',3))
        except (ValueError,OSError,KeyError,sqlite3.Error) as error:
            result={'status':'error','availability':'unknown','error':str(error),
                    'corpus':{'id':case['version'],'label':None},
                    'host':{'system':platform.system(),'architecture':platform.machine()},
                    'target':{'project_type':case['project_type'],'platform':case['platform'],
                              'platform_role':'server' if case['project_type']=='web' else 'runtime'}}
        error=None
        try:
            assess(case,result)
        except AssertionError as failure:
            error=str(failure)
        (args.output/(case['id']+'.json')).write_text(json.dumps({'case':case,'result':result,'assessment_error':error},indent=2)+'\n')
        record={'id':case['id'],'passed':error is None,'error':error,'seconds':round(time.monotonic()-at,4),'evidence':case['id']+'.json'}
        records.append(record)
        print(json.dumps(record),flush=True)
    summary={'recorded_at':datetime.now(timezone.utc).isoformat(),'cases_sha256':sha(args.cases.read_bytes()),
             'total':len(records),'passed':sum(r['passed'] for r in records),'seconds':round(time.monotonic()-start,3),
             'scope':'Curated documentation retrieval/label/provenance checks; no runtime validation or semantic quality score.',
             'records':records}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if summary['passed']!=summary['total']:
        raise SystemExit(1)


if __name__=='__main__': main()
