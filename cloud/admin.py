"""Operator tools; never reachable as public API routes."""
import argparse
import json
import time
from sqlalchemy import select, update, text
from .config import Settings
from .db import Database, invites, accounts, jobs, calls, events, budgets


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    invite=sub.add_parser('invite'); invite.add_argument('email')
    revoke=sub.add_parser('uninvite'); revoke.add_argument('email')
    sub.add_parser('report')
    sub.add_parser('init-local')
    sub.add_parser('configure-chat')
    args=parser.parse_args()
    settings=Settings(); settings.validate(); db=Database(settings)
    if args.command=='init-local':
        if not settings.dev: raise ValueError('Apply the migration to production instead.')
        db.initialize(); return
    if args.command=='configure-chat':
        if settings.dev: raise ValueError('Configure chat only in the dedicated hosted project.')
        with db.transaction() as c:
            c.execute(text("INSERT INTO public.pilot_oauth_config (id, resource) VALUES ('mcp', :resource) ON CONFLICT (id) DO UPDATE SET resource = EXCLUDED.resource"),
                      {'resource':settings.mcp_resource})
        print('OAuth resource configured: '+settings.mcp_resource)
        print('Enable the Lectic token hook and OAuth server in Supabase, then set LECTIC_CHAT_ENABLED=1.'); return
    if args.command in {'invite','uninvite'}:
        email=args.email.strip().lower()
        if '@' not in email or len(email)>320: raise ValueError('Use a valid email.')
        with db.transaction() as c:
            existing=c.execute(select(invites).where(invites.c.id==email)).first()
            enabled=int(args.command=='invite')
            if existing: c.execute(update(invites).where(invites.c.id==email).values(enabled=enabled))
            else: c.execute(invites.insert().values(id=email,enabled=enabled))
        print('Invitation '+('enabled' if enabled else 'revoked'))
    elif args.command=='report':
        with db.engine.connect() as c:
            users=c.execute(select(accounts)).mappings().all()
            measurements=c.execute(select(events)).mappings().all()
            ledger=c.execute(select(budgets)).mappings().all()
            uncertain=c.execute(select(calls).where(calls.c.status=='reserved')).mappings().all()
        report=[]
        for user in users:
            own=[e for e in measurements if e['owner']==user['id']]
            first=min((e['created'] for e in own if e['name']=='first_visit'),default=None)
            useful=min((e['created'] for e in own if e['name']=='result_useful'),default=None)
            report.append({'account':user['id'],'first_useful_seconds':round(useful-first,1) if first and useful else None,
                           'fallback_events':sum(e['name']=='capture_fallback' for e in own),
                           'return_days':len({time.strftime('%Y-%m-%d',time.gmtime(e['created'])) for e in own if e['name']=='return_visit'})})
        print(json.dumps({'participants':report,'spending':[{"month":r['id'],"committed_dollars":r['committed']/1e6} for r in ledger],
                          'uncertain_calls':len(uncertain),'coaching_not_measured':'Observe sessions separately.'},indent=2))


if __name__=='__main__': main()
