#!/usr/bin/env python3
"""Read-only, per-request XDOX keyword retrieval with local source provenance."""
import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform as host_platform
import re
import sqlite3

PROJECTS = {'desktop', 'web', 'mobile', 'console'}
PLATFORMS = {'macos', 'windows', 'linux', 'ios', 'android'}
LABEL = re.compile(r'^\s*\.\. _([^:]+):\s*$', re.M)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(value):
    value = re.sub(r':\w+:`([^`]+)`', lambda m: m[1].split('<')[0].strip(), value)
    return re.sub(r'[*`]', '', value).strip()


def headings(lines):
    return [(i, clean(lines[i])) for i in range(len(lines)-1)
            if lines[i].strip() and re.fullmatch(r'[=\-~*^]{3,}', lines[i+1].strip())
            and not re.fullmatch(r'[=\-~*^]+', lines[i].strip())]


def reference(root, path, start=0, end=None, anchor=None):
    data = path.read_bytes()
    lines = data.decode('utf-8').splitlines()
    end = len(lines) if end is None else end
    relative = path.relative_to(root).as_posix()
    result = {'file': str(path), 'relative_file': relative, 'line_start': start+1,
              'line_end': end, 'sha256': sha(data), 'anchor': anchor}
    # Publish a URL only when its page and anchor exist in this installed bundle.
    page = relative.removeprefix('_sources/').removesuffix('.rst.txt') + '.html'
    html = root / page
    html_anchor = anchor.replace('.', '-') if anchor else None
    if html.is_file() and (not anchor or re.search(r'\bid=[\'\"]' + re.escape(html_anchor) + r'[\'\"]', html.read_text())):
        result['html_anchor'] = html_anchor
        result['online_url'] = 'https://documentation.xojo.com/' + page + (('#'+html_anchor) if anchor else '')
        result['online_version_warning'] = 'Live website may differ; local file/hash defines this corpus.'
    return result


class Lookup:
    def __init__(self, registry, version, project_type, platform):
        if project_type not in PROJECTS or platform not in PLATFORMS:
            raise ValueError('Unknown project type or platform')
        valid_os = {'ios', 'android'} if project_type == 'mobile' else {'macos', 'windows', 'linux'}
        if platform not in valid_os:
            raise ValueError('Platform must be a mobile OS for Mobile, or a host/server OS for Desktop/Console/Web')
        config_path = Path(registry).resolve()
        config = json.loads(config_path.read_text())
        if config.get('schema') != 1 or version not in config.get('corpora', {}):
            raise ValueError('Requested corpus is not registered: ' + version)
        corpus = config['corpora'][version]
        def local(value):
            return (config_path.parent / Path(value).expanduser()).resolve()
        self.root = local(corpus['root'])
        self.database = local(config['database'])
        self.version = version
        self.label = corpus['label']
        self.corpus_hash = corpus['llms_sha256']
        self.target = {'project_type': project_type, 'platform': platform,
                       'platform_role': 'server' if project_type == 'web' else 'runtime'}
        self.host = {'system': host_platform.system(), 'architecture': host_platform.machine()}
        if self.root.parent.name != self.label:
            raise ValueError('Corpus directory label differs from registered Xojo version')
        if sha((self.root/'llms-full.txt').read_bytes()) != corpus['llms_sha256']:
            raise ValueError('Corpus fingerprint changed; review and register the intended documentation')
        if not self.database.is_file():
            raise ValueError('XDOX database not found')
        self.pages = defaultdict(list)
        self.names = defaultdict(list)
        self.cache = {}
        self.source_hashes = {}
        for path in sorted((self.root/'_sources').rglob('*.rst.txt')):
            lines = self.lines(path)
            titles = headings(lines)
            if titles:
                self.pages[titles[0][1].casefold()].append(path)
            self.names[path.name[:-8].casefold()].append(path)
        if not self.names:
            raise ValueError('No installed RST source files')
        with closing(self.connect()) as db:
            if not db.execute('select 1 from chunks where docs_version=? limit 1', (self.label,)).fetchone():
                raise ValueError('Requested version is not indexed in XDOX: ' + self.label)

    def connect(self):
        db = sqlite3.connect(self.database.as_uri()+'?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        db.execute('pragma query_only=on')
        return db

    def lines(self, path):
        if path not in self.cache:
            data = path.read_bytes()
            self.cache[path] = data.decode('utf-8').splitlines()
            self.source_hashes[path] = sha(data)
        return self.cache[path]

    def source_ref(self, path, *section):
        self.lines(path)
        result = reference(self.root,path,*section)
        if result['sha256'] != self.source_hashes[path]:
            raise ValueError('Documentation source changed; recreate the lookup snapshot')
        return result

    def envelope(self, operation, request):
        if sha((self.root/'llms-full.txt').read_bytes()) != self.corpus_hash:
            raise ValueError('Corpus fingerprint changed; recreate and review the lookup snapshot')
        return {'schema': 1, 'operation': operation, 'request': request,
                'corpus': {'id': self.version, 'label': self.label, 'root': str(self.root),
                           'llms_sha256':self.corpus_hash},
                'target': self.target, 'host': self.host, 'results': [],
                'availability': 'unknown', 'status': 'no_match',
                'limitation': 'Documentation evidence only; no target compilation or execution.'}

    def section(self, path, member=None, section_title=None):
        lines = self.lines(path)
        anchors = [(i, m[1]) for i,line in enumerate(lines) if (m := LABEL.fullmatch(line))]
        if member:
            wanted = path.name[:-8].casefold()+'.'+member.casefold()
            found = [(i,a) for i,a in anchors if a.casefold()==wanted]
            if not found:
                return None
            start, anchor = found[0]
            end = next((i for i,_ in anchors if i>start),len(lines))
            # Stop at a subsequent major heading (not the transition under label).
            end = min([end]+[i for i,_ in headings(lines) if i>start and i<end])
        elif section_title:
            found = [(i,t) for i,t in headings(lines) if t.casefold()==section_title.casefold()]
            if len(found)!=1:
                return None
            start,_ = found[0]
            end = next((i for i,_ in headings(lines) if i>start),len(lines))
            anchor = None
        else:
            start = 0
            end = next((i for i,a in anchors if '.' in a), len(lines))
            anchor = None
        return start,end,anchor

    def result(self, path, section, title):
        start,end,anchor = section
        lines = self.lines(path)
        text = '\n'.join(lines[start:end])
        source = self.source_ref(path,start,end,anchor)
        compat = {}
        compat_refs = []
        for i,line in enumerate(lines):
            m = re.fullmatch(r'\s*"\*\*(Project Types|Operating Systems)\*\*",\s*"([^"]+)"\s*',line)
            if m:
                compat[m[1]] = m[2]
                compat_refs.append(self.source_ref(path,i,i+1))
        kind = 'release_notes' if '/release_notes/' in str(path) else ('api' if '/api/' in str(path) else 'guide')
        available = 'unknown'
        basis = 'No explicit compatible table; scope is unresolved.'
        if kind=='api' and set(compat)=={'Project Types','Operating Systems'}:
            projects = [x.strip().casefold() for x in compat['Project Types'].split(',')]
            systems = [x.strip().casefold() for x in compat['Operating Systems'].split(',')]
            system = {'macos':'macos','windows':'windows','linux':'linux','ios':'ios','android':'android'}[self.target['platform']]
            okay = ('all' in projects or self.target['project_type'] in projects) and ('all' in systems or system in systems)
            understood = set(projects) <= PROJECTS | {'all'} and set(systems) <= PLATFORMS | {'all'}
            available = ('documented_compatible' if okay else 'documented_incompatible') if understood else 'unknown'
            basis = 'Page Compatibility table; member notes may qualify this.'
            # Only explicit positive "OS-only" phrases are mechanically scoped.
            only = re.findall(r'\b(macOS|Windows|Linux|iOS|Android)[ -]only\b',text,re.I)
            if only and understood and okay and not re.search(r'\b(not|except|unless)\b',text,re.I):
                available = 'unknown'
                basis = 'Platform-specific prose requires source review.'
                if len(set(x.lower() for x in only)) == 1:
                    available = 'documented_compatible' if okay and system == only[0].lower() else 'documented_incompatible'
                basis += ' Explicit OS-only restriction in the selected section.'
            elif available != 'documented_incompatible' and re.search(r'\b(macOS|Windows|Linux|iOS|Android)\b',text,re.I) and anchor:
                available = 'unknown'
                basis = 'Member contains platform-specific prose; inspect its source before an availability decision.'
        deprecated = '/deprecated/' in str(path)
        notices = [{'text':line.strip(), 'source':self.source_ref(path,i,i+1)}
                   for i,line in enumerate(lines) if re.search(r'was deprecated|deprecated in|use .*replacement',line,re.I)]
        result = {'title':title,'kind':kind,'corpus_version':self.label,'target':self.target,
                  'availability':available,'availability_basis':basis,'compatibility':compat,
                  'historical_release':path.name[:-8] if kind=='release_notes' else None,
                  'compatibility_sources':compat_refs,'deprecated':deprecated,
                  'deprecation_notices':notices,'source':source,'text':text[:6000],
                  'text_truncated':len(text)>6000}
        return result

    def lookup(self, class_name, member=None):
        if not re.fullmatch(r'[\w.]+',class_name) or (member and not re.fullmatch(r'[\w.]+',member)):
            raise ValueError('Class/member must be identifiers, supplied separately')
        out = self.envelope('lookup',{'class_name':class_name,'member':member})
        candidates = self.names.get(class_name.casefold(),[])
        if len(candidates)!=1:
            out['status'] = 'ambiguous' if candidates else 'no_match'
            out['candidate_files'] = [str(p) for p in candidates]
            out['reason'] = 'No unambiguous exact page; no Desktop/Web prefix substitution.'
            return out
        path = candidates[0]
        section = self.section(path,member)
        if section is None:
            out['reason'] = 'Member not documented on this page; this does not establish API absence.'
            out['inspected_source'] = self.source_ref(path)
            return out
        result = self.result(path,section,class_name+('.'+member if member else ''))
        # A parent reference is supporting documentation, not a declaration-site assertion.
        parent = re.search(r':doc:`([^`<]+)<(/[^>]+)>` parent class', '\n'.join(self.lines(path)))
        if member and parent:
            parent_path = self.root/'_sources'/(parent[2].lstrip('/')+'.rst.txt')
            if parent_path.is_file() and (parent_section := self.section(parent_path,member)):
                result['also_documented_on_parent'] = {'class_name':parent[1], 'source':self.source_ref(parent_path,*parent_section)}
        out.update(status='found',results=[result],availability=result['availability'])
        return out

    def chunk_window(self, path, text, query):
        # XDOX cleans RST during indexing. Verify a unique normalized source line
        # before citing a part/chunk whose title cannot identify a section.
        def normalized(line):
            return ' '.join(re.findall(r'[^\W_]+', clean(line).casefold()))
        lines = self.lines(path)
        normalized_lines = [normalized(line) for line in lines]
        tokens = set(re.findall(r'\w+', query.casefold()))
        choices = [line for line in text.splitlines() if len(normalized(line)) >= 40]
        choices.sort(key=lambda line: len(tokens & set(re.findall(r'\w+',line.casefold()))), reverse=True)
        for line in choices:
            needle = normalized(line)
            matches = [i for i,value in enumerate(normalized_lines) if needle == value]
            if len(matches) == 1:
                at = matches[0]
                return max(0,at-2),min(len(lines),at+12),None
        return None

    def search(self, query, max_results=5):
        if not query.strip() or not 1<=max_results<=20:
            raise ValueError('Provide a query and max_results from 1 to 20')
        # User text is data: quote lexical tokens rather than accepting FTS syntax.
        tokens = re.findall(r'\w+',query)
        if not tokens:
            raise ValueError('Query needs at least one word')
        expression = ' AND '.join('"'+t+'"' for t in tokens)
        out = self.envelope('search',{'query':query,'max_results':max_results})
        out['retrieval'] = {'tier':'xdox_fts5_bm25','database':str(self.database),
                            'version_filter':self.label,'candidate_limit':200,
                            'includes_version_independent_chunks':False,
                            'excluded_target_mismatches':0,'unresolved_sources':0}
        with closing(self.connect()) as db:
            rows = db.execute('''select c.id,c.title,c.source,c.chunk_text,c.docs_version,bm25(chunks_fts) as rank
                from chunks_fts join chunks c on c.id=chunks_fts.rowid
                where chunks_fts match ? and c.docs_version=? order by rank,c.id limit 200''',
                (expression,self.label)).fetchall()
        seen=set()
        for row in rows:
            parts = re.sub(r' \(part \d+\)$','',row['title']).split(' > ')
            candidates = self.pages.get(parts[0].casefold(),[])
            if len(candidates)!=1:
                out['retrieval']['unresolved_sources']+=1
                continue
            path=candidates[0]
            section=None
            if len(parts)>1:
                section=self.section(path,parts[-1]) or self.section(path,section_title=parts[-1])
            mapping = 'section' if section else 'page_overview_only'
            if section is None:
                section = self.chunk_window(path,row['chunk_text'],query)
                if section:
                    mapping = 'unique_normalized_source_line'
            if section is None and len(parts)>1:
                out['retrieval']['unresolved_sources']+=1
                continue
            section=section or self.section(path)
            key=(path,section)
            if key in seen:
                continue
            seen.add(key)
            result=self.result(path,section,row['title'])
            if result['availability']=='documented_incompatible':
                out['retrieval']['excluded_target_mismatches']+=1
                continue
            result['index_hit']={'chunk_id':row['id'],'title':row['title'],'source':row['source'],
                                 'docs_version':row['docs_version'],'sha256':sha(row['chunk_text'].encode()),
                                 'bm25':row['rank'],'mapping':mapping,'text_origin':'installed RST; chunk used for ranking only'}
            out['results'].append(result)
            if len(out['results'])>=max_results:
                break
        out['status']='found' if out['results'] else 'no_match'
        # Search hits (especially historical notes) are not an overall availability verdict.
        return out


def register(database,root,version,output):
    root=Path(root).expanduser().resolve()
    label='Xojo '+version
    if root.parent.name!=label:
        raise ValueError('Docs root must be inside the matching Xojo version directory')
    value={'schema':1,'database':str(Path(database).expanduser().resolve()),'corpora':{
        version:{'label':label,'root':str(root),'llms_sha256':sha((root/'llms-full.txt').read_bytes())}}}
    output=Path(output)
    if output.exists():
        raise ValueError('Registry output already exists; review before updating')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(value,indent=2)+'\n')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    init=commands.add_parser('register')
    for name in ['database','docs-root','version','output']:init.add_argument('--'+name,required=True)
    for name in ['lookup','search']:
        p=commands.add_parser(name)
        for arg in ['registry','version','project-type','platform']:p.add_argument('--'+arg,required=True)
        if name=='lookup':
            p.add_argument('--class-name',required=True);p.add_argument('--member')
        else:
            p.add_argument('--query',required=True);p.add_argument('--max-results',type=int,default=5)
    args=parser.parse_args()
    try:
        if args.command=='register':
            result=register(args.database,args.docs_root,args.version,args.output)
        else:
            service=Lookup(args.registry,args.version,args.project_type,args.platform)
            result=service.lookup(args.class_name,args.member) if args.command=='lookup' else service.search(args.query,args.max_results)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,KeyError,sqlite3.Error) as error:
        print(json.dumps({'status':'error','availability':'unknown','error':str(error),
                          'corpus':{'id':args.version,'label':None},
                          'host':{'system':host_platform.system(),'architecture':host_platform.machine()},
                          'target':{'project_type':getattr(args,'project_type',None),
                                    'platform':getattr(args,'platform',None),
                                    'platform_role':'server' if getattr(args,'project_type',None)=='web' else 'runtime'}}))
        raise SystemExit(1)


if __name__=='__main__':
    main()
