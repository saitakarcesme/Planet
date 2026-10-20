"""Known capability selection, execution and private timing evidence."""
import json
import re
from pathlib import Path
import time
from .skills import SKILLS, BY_ID, match, validate
from .capabilities import Executor, CapabilityError
from .desktop import ROOT

def direct_plan(text):
    """Compose up to four wholly recognized clauses, never a partial match."""
    direct=match(text)
    if direct:return [(*direct,'alias')]
    parts=re.split(r'\s+(?:and then|and|then|ve sonra|ve|sonra|ardından|ardindan)\s+',text.strip(),flags=re.I)
    if not 2<=len(parts)<=4:return None
    matches=[match(part) for part in parts]
    return [(*item,'alias-chain') for item in matches] if all(matches) else None


def resolved_plan(text):
    """A wildcard application name is direct only if the installed catalog agrees."""
    plan=direct_plan(text)
    if plan and any(id.startswith('app.') for id,_,_ in plan):
        resolver=Executor()
        try:
            for id,args,_ in plan:
                if id.startswith('app.'):resolver.app_id(args['app'])
        except CapabilityError:
            return None
    return plan


def select(text, decision=None, generate=None, aliases=True):
    direct=match(text) if aliases else None
    if direct:return (*direct,'alias')
    if not decision:return None
    options={s['id']:s['title'] for s in SKILLS}
    options['other']='Unknown, ambiguous, compound/multiple tasks, or not exactly one capability. Use the general planner.'
    chosen,p=decision({'human_request':text},options,
        'Select EXACTLY one fully matching capability. Choose other for multiple actions, extra conditions, absent scope, unknown or ambiguous requests. Do not discard any requirement to fit a capability.')
    if chosen=='other' or p<.97 or chosen not in BY_ID:return None
    skill=BY_ID[chosen]
    if chosen=='media.search':
        scope, confidence=decision({'human_request':text},{
            'resume':'Play any music in Spotify. No named artist, song, album, playlist, personal collection, genre, mood, exclusion or other condition.',
            'named':'Play a specific named artist or song in Spotify, with no additional conditions.',
            'other':'Personal collection, playlist, album, genre, mood, extra condition, ambiguous target or multiple tasks.'
        },'Classify the WHOLE request. Do not discard any qualifier. A polite request for unspecified music is resume, not a literal search.')
        # This three-way gate has a different probability distribution from the
        # 101-way capability selector. Keep its separately tested threshold.
        if confidence<.90 or scope=='other':return None
        if scope=='resume':
            return chosen,{'query':'some music'},'semantic'
    if skill['params']:
        if generate is None:return None
        args=generate(skill,text)
        if args is None:return None
    else:args={}
    validate(chosen,args)
    return chosen,args,'semantic'


def attempt(text,emit,context=None,semantic=True):
    from .bridge import decision, generator, http
    start=time.monotonic()
    def extract(skill,text):
        base,model=generator()
        # A compact single-tool call, with no desktop dump or long agent prompt.
        definition={'type':'function','function':{'name':'parameters','description':skill['title'],
            'parameters':{'type':'object','properties':{k:{'type':v} for k,v in skill['params'].items()},'required':list(skill['params']),'additionalProperties':False}}}
        catalog=''
        if skill['id'].startswith('app.'):
            catalog='\nFor app, resolve the explicitly requested installed application using this catalog. Use its exact ID. Do not substitute another app for one that is absent. If ambiguous, return no tool call.\n'+json.dumps(Executor().desktop.catalog())
        response=http(base+'/chat/completions',{'model':model,'messages':[
            {'role':'system','content':'Extract parameters literally from the human request for the named capability. Preserve paths, artist names and user text. Exclude polite conversational wording from an artist/song target. Do not invent missing values. If missing or ambiguous, return no tool call. Never execute anything.'+catalog},
            {'role':'user','content':text}], 'tools':[definition],'temperature':0,'max_tokens':250,'chat_template_kwargs':{'enable_thinking':False}},timeout=10)
        calls=response['choices'][0]['message'].get('tool_calls') or []
        if len(calls)!=1 or calls[0]['function']['name']!='parameters':return None
        raw=calls[0]['function']['arguments'];return json.loads(raw) if isinstance(raw,str) else raw
    try:
        plan=resolved_plan(text)
        if plan is None:
            selection=select(text,decision if semantic else None,extract,aliases=False)
            if not selection:return None
            plan=[selection]
    except (OSError,ValueError,KeyError,RuntimeError):return None
    emit('state',phase='acting',message=BY_ID[plan[0][0]]['title'],desktop=True)
    time.sleep(.08) # release overlay keyboard focus before native operations
    executor=Executor(target_window=(context or {}).get('window'))
    try:
        completed=[];messages=[]
        for id,args,source in plan:
            emit('state',phase='acting',message=BY_ID[id]['title'],desktop=True)
            value=executor.run(id,args)
            completed.append({'id':id,'arguments':args,'result':value})
            if value.get('message'):messages.append(value['message'])
        answer=(True,'\n\n'.join(messages),'done')
    except Exception as error:
        value={'verified':False,'error':str(error)[:400]}
        answer=(False,'Could not complete this capability: '+str(error)[:300]+(' Earlier steps were kept.' if completed else ''),'blocked')
    finally:
        executor.desktop.restore_windows()
    folder=ROOT/'.planet-runs';folder.mkdir(exist_ok=True,mode=0o700)
    path=folder/('fast-'+str(time.time_ns())+'.json')
    path.write_text(json.dumps({'request':text,'skill':id,'arguments':args,'source':source,'steps':completed,'elapsed_s':round(time.monotonic()-start,4),'result':value},ensure_ascii=False,indent=2));path.chmod(0o600)
    emit('capability',id=id,source=source,elapsed=round(time.monotonic()-start,4))
    return answer
