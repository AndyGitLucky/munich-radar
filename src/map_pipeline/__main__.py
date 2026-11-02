import argparse
import json
from .core import Workspace,load


def main():
    parser=argparse.ArgumentParser(description='Reproduce the original atlas and replace individual native sections.')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('inspect')
    build=sub.add_parser('build');build.add_argument('--baseline',action='store_true');build.add_argument('--fresh',action='store_true');build.add_argument('--publish',action='store_true')
    verify=sub.add_parser('verify');verify.add_argument('release')
    serve=sub.add_parser('serve');serve.add_argument('--port',type=int,default=8015)
    prepare=sub.add_parser('prepare');prepare.add_argument('tile');prepare.add_argument('version');prepare.add_argument('--task',required=True);prepare.add_argument('--rect',nargs=4,type=int);prepare.add_argument('--allow-landmarks',action='store_true')
    take=sub.add_parser('import');take.add_argument('tile');take.add_argument('version');take.add_argument('--image',required=True)
    preview=sub.add_parser('preview');preview.add_argument('tile');preview.add_argument('version')
    review=sub.add_parser('review');review.add_argument('tile');review.add_argument('version');review.add_argument('--decision',choices=['accept','reject'],required=True);review.add_argument('--note',required=True);review.add_argument('--allow-warnings',action='store_true')
    activate=sub.add_parser('activate');activate.add_argument('tile');activate.add_argument('version')
    rollback=sub.add_parser('rollback');target=rollback.add_mutually_exclusive_group(required=True);target.add_argument('--tile');target.add_argument('--release')
    args=parser.parse_args();workspace=Workspace()
    if args.command=='serve':
        from .server import serve
        serve(args.port);return
    with workspace.lock():
        if args.command=='inspect':result=workspace.inspect()
        elif args.command=='prepare':result=workspace.prepare(args.tile,args.version,args.task,args.rect,args.allow_landmarks)
        elif args.command=='import':result=workspace.import_image(args.tile,args.version,args.image)
        elif args.command=='review':result=workspace.review(args.tile,args.version,args.decision,args.note,args.allow_warnings)
        else:
            from .render import build,publish,validate_release
            if args.command=='build':
                id=build(workspace,workspace.original_state() if args.baseline else None,args.fresh)
                result=publish(workspace,id) if args.publish else {'release':id,'status':'built and verified; live map unchanged'}
            elif args.command=='verify':
                folder=validate_release(workspace,args.release)
                from .quality import verify_release
                quality,_=verify_release(workspace,folder,load(folder/'state.json'),load(folder/'assembly.json'),load(folder/'manifest.json'));result=quality
            elif args.command=='preview':
                id=build(workspace,workspace.proposed_state(args.tile,args.version));workspace.review_page(args.tile,args.version,id)
                result={'release':id,'review':f'/atlas/candidates/{args.tile}/{args.version}/','status':'preview only; live map unchanged'}
            elif args.command=='activate':
                state=workspace.proposed_state(args.tile,args.version);workspace.validate_state(state,require_review=True)
                id=build(workspace,state);workspace.review_page(args.tile,args.version,id);result=publish(workspace,id)
            elif args.command=='rollback':
                if args.release:result=publish(workspace,args.release)
                else:
                    state=workspace.state()
                    if args.tile not in state['tiles']:raise ValueError('Unknown section')
                    state['tiles'][args.tile]=workspace.original_state()['tiles'][args.tile]
                    result=publish(workspace,build(workspace,state))
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    import sys
    try:main()
    except (ValueError,RuntimeError,FileNotFoundError) as error:
        print('Kartenpipeline: '+str(error),file=sys.stderr);raise SystemExit(2)
