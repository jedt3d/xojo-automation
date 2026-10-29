from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from xdox_lookup import Lookup, register, sha


@contextmanager
def database(path):
    with closing(sqlite3.connect(path)) as db:
        with db:
            yield db


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.base=Path(self.temp.name)
        self.db=self.base/'xdox.db'
        with database(self.db) as db:
            db.executescript('''create table chunks(id integer primary key,title text,source text,chunk_text text,docs_version text);
                create virtual table chunks_fts using fts5(title,chunk_text,content='chunks',content_rowid='id');
                create table metadata(key text,value text);
                insert into metadata values('active_docs_version','Xojo 2025r1');''')
        self.roots={}
        corpora={}
        for version in ['2025r1','2026r3']:
            root=self.base/('Xojo '+version)/'Documentation'
            root.mkdir(parents=True)
            (root/'llms-full.txt').write_text('Synthetic documentation '+version)
            self.roots[version]=root
            self.page(version,'api/button','Button','Enabled',f'Value for {version}.')
            corpora[version]={'label':'Xojo '+version,'root':str(root),'llms_sha256':sha((root/'llms-full.txt').read_bytes())}
            self.chunk(version,'Button > Enabled',f'VersionMarker {version}')
        self.registry=self.base/'registry.json'
        self.registry.write_text(json.dumps({'schema':1,'database':str(self.db),'corpora':corpora}))

    def tearDown(self):
        self.temp.cleanup()

    def page(self,version,relative,name,member,description,projects='Desktop',systems='All',extra=''):
        root=self.roots[version]
        path=root/'_sources'/(relative+'.rst.txt')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(f'''{'='*len(name)}
{name}
{'='*len(name)}

Description
-----------
Synthetic page.

.. _{name.lower()}.{member.lower()}:

----

{name}.{member}

{description}

Compatibility
-------------

  "**Project Types**", "{projects}"
  "**Operating Systems**", "{systems}"

{extra}
''')
        html=root/(relative+'.html')
        html.parent.mkdir(parents=True,exist_ok=True)
        html.write_text(f'<div id="{name.lower()}-{member.lower()}">Synthetic</div>')
        return path

    def chunk(self,version,title,text):
        with database(self.db) as db:
            row=db.execute('insert into chunks(title,source,chunk_text,docs_version) values(?,?,?,?)',
                           (title,'llms-full.txt > '+title.split(' > ')[0],text,'Xojo '+version))
            db.execute('insert into chunks_fts(rowid,title,chunk_text) values(?,?,?)',(row.lastrowid,title,text))

    def service(self,version='2026r3',project='desktop',platform='macos'):
        return Lookup(self.registry,version,project,platform)

    def test_request_version_overrides_global_picker_without_writes(self):
        before=self.db.read_bytes()
        current=self.service().search('VersionMarker',5)
        old=self.service('2025r1').search('VersionMarker',5)
        self.assertEqual(current['results'][0]['index_hit']['docs_version'],'Xojo 2026r3')
        self.assertIn('2026r3',current['results'][0]['text'])
        self.assertIn('2025r1',old['results'][0]['text'])
        self.assertEqual(before,self.db.read_bytes())

    def test_unknown_version_fails_without_newest_fallback(self):
        with self.assertRaisesRegex(ValueError,'not registered'):
            self.service('2024r1')

    def test_registered_but_unindexed_version_fails(self):
        with database(self.db) as db:
            db.execute("delete from chunks where docs_version='Xojo 2026r3'")
        with self.assertRaisesRegex(ValueError,'not indexed'):
            self.service()

    def test_changed_bundle_fingerprint_is_rejected(self):
        (self.roots['2026r3']/'llms-full.txt').write_text('different bundle')
        with self.assertRaisesRegex(ValueError,'fingerprint changed'):
            self.service()

    def test_verified_anchor_lines_and_hash(self):
        result=self.service().lookup('Button','Enabled')['results'][0]
        ref=result['source'];path=Path(ref['file'])
        lines=path.read_text().splitlines()
        self.assertEqual(result['text'],'\n'.join(lines[ref['line_start']-1:ref['line_end']]))
        self.assertEqual(ref['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(ref['online_url'].endswith('#button-enabled'))
        self.assertNotIn('Compatibility',result['text'])

    def test_source_anchor_without_html_is_still_inspectable(self):
        (self.roots['2026r3']/'api/button.html').unlink()
        result=self.service().lookup('Button','Enabled')['results'][0]
        self.assertNotIn('online_url',result['source'])
        self.assertEqual(result['source']['anchor'],'button.enabled')

    def test_target_mismatch_is_labeled_and_filtered_from_search(self):
        service=self.service(project='web',platform='linux')
        self.assertEqual(service.lookup('Button','Enabled')['availability'],'documented_incompatible')
        result=service.search('VersionMarker')
        self.assertEqual(result['results'],[])
        self.assertEqual(result['retrieval']['excluded_target_mismatches'],1)
        self.assertEqual(result['target']['platform_role'],'server')

    def test_os_only_and_platform_prose_are_scoped_conservatively(self):
        self.page('2026r3','api/button','Button','Enabled','This is a macOS-only property.')
        self.assertEqual(self.service(platform='windows').lookup('Button','Enabled')['availability'],'documented_incompatible')
        self.page('2026r3','api/button','Button','Enabled','This is not a macOS-only property.')
        self.assertEqual(self.service().lookup('Button','Enabled')['availability'],'unknown')

    def test_unrecognized_compatibility_does_not_assert_unsupported(self):
        self.page('2026r3','api/button','Button','Enabled','Value.',systems='FutureOS')
        self.assertEqual(self.service().lookup('Button','Enabled')['availability'],'unknown')

    def test_deprecation_and_parent_reference_have_sources(self):
        self.page('2026r3','api/base','Base','Enabled','Base value.')
        self.page('2026r3','api/deprecated/oldbutton','OldButton','Enabled','Value.',
                  extra='.. warning:: This item was deprecated in version 2021r3.\n:doc:`Base</api/base>` parent class')
        r=self.service().lookup('OldButton','Enabled')['results'][0]
        self.assertTrue(r['deprecated'])
        self.assertEqual(r['also_documented_on_parent']['class_name'],'Base')
        self.assertEqual(len(r['deprecation_notices']),1)

    def test_missing_class_member_and_exact_name_behavior(self):
        service=self.service()
        self.assertEqual(service.lookup('UnknownThing')['availability'],'unknown')
        self.assertEqual(service.lookup('Button','Missing')['status'],'no_match')
        self.assertIn('inspected_source',service.lookup('Button','Missing'))
        self.assertEqual(service.lookup('DesktopButton')['status'],'no_match')

    def test_duplicate_pages_are_ambiguous(self):
        self.page('2026r3','api/other/button','Button','Enabled','Other value.')
        self.assertEqual(self.service().lookup('Button')['status'],'ambiguous')
        self.assertEqual(self.service().search('VersionMarker')['results'],[])

    def test_release_history_stays_unknown_and_maps_chunk_to_source_line(self):
        description='Android introspection details that are long enough to make a uniquely identifiable source line.'
        self.page('2026r3','resources/release_notes/2024r3','Xojo 2024r3 Release Notes','Item',description)
        self.chunk('2026r3','Xojo 2024r3 Release Notes > Unmapped (part 2)',description)
        r=self.service().search('Android introspection')['results'][0]
        self.assertEqual(r['availability'],'unknown')
        self.assertEqual(r['historical_release'],'2024r3')
        self.assertIn(description,r['text'])
        self.assertEqual(r['index_hit']['mapping'],'unique_normalized_source_line')

    def test_fts_syntax_is_query_text_and_limits_are_bounded(self):
        service=self.service()
        self.assertEqual(service.search('" OR VersionMarker')['results'],[])
        with self.assertRaises(ValueError): service.search('VersionMarker',21)
        with self.assertRaises(ValueError): service.search('!!!')

    def test_invalid_target_pair_is_rejected(self):
        with self.assertRaises(ValueError): self.service(project='desktop',platform='android')

    def test_reused_lookup_rejects_changed_source(self):
        service=self.service()
        self.page('2026r3','api/button','Button','Enabled','Changed after snapshot.')
        with self.assertRaisesRegex(ValueError,'source changed'):
            service.lookup('Button','Enabled')

    def test_unmapped_chunk_is_not_presented_as_verified_source_text(self):
        self.chunk('2026r3','Button > UnknownSection','Invented unmatched words with no source equivalent anywhere.')
        result=self.service().search('Invented unmatched')
        self.assertEqual(result['status'],'no_match')
        self.assertEqual(result['availability'],'unknown')
        self.assertEqual(result['retrieval']['unresolved_sources'],1)

    def test_cli_scope_error_is_structured_and_labeled(self):
        cli=Path(__file__).resolve().parents[1]/'scripts/xdox_lookup.py'
        run=subprocess.run([sys.executable,str(cli),'lookup','--registry',str(self.registry),
                            '--version','2024r1','--project-type','web','--platform','linux',
                            '--class-name','Button'],capture_output=True,text=True)
        self.assertEqual(run.returncode,1)
        result=json.loads(run.stdout)
        self.assertEqual(result['corpus']['id'],'2024r1')
        self.assertEqual(result['target']['platform_role'],'server')
        self.assertIn('architecture',result['host'])
        self.assertEqual(result['availability'],'unknown')

    def test_reused_lookup_rejects_changed_corpus_fingerprint(self):
        service=self.service()
        (self.roots['2026r3']/'llms-full.txt').write_text('Changed after registration.')
        with self.assertRaisesRegex(ValueError,'fingerprint changed'):
            service.search('VersionMarker')

    def test_registration_does_not_overwrite_existing_registry(self):
        with self.assertRaisesRegex(ValueError,'already exists'):
            register(self.db,self.roots['2026r3'],'2026r3',self.registry)


if __name__=='__main__': unittest.main()
