"""Exercise the real CLI's reviewed example, section rollback and release rollback.

Requires the recorded r03c05/shape-01 example. Restores the initial release unless
--leave-example is explicitly supplied. It does not generate any artwork.
"""
import argparse
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.map_pipeline.core import ROOT,Workspace,load,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--leave-example',action='store_true');args=parser.parse_args()
    workspace=Workspace();initial=load(workspace.root/'current.json')['release'];initial_state=workspace.state()
    commands=[];success=False;example=None
    def run(*arguments):
        command=[sys.executable,'-X','utf8','-m','src.map_pipeline',*arguments]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
        current=load(workspace.root/'current.json')['release']
        commands.append({'arguments':list(arguments),'exitCode':completed.returncode,'release':current,'output':completed.stdout})
        print('PASS:', ' '.join(arguments), '->',current,flush=True)
        return current
    try:
        example=run('activate','r03c05','shape-01')
        assert workspace.state()['tiles']['r03c05']['version']=='shape-01'
        for id,item in initial_state['tiles'].items():
            if id!='r03c05':assert workspace.state()['tiles'][id]==item,'Unrelated source selection changed'
        original=run('rollback','--tile','r03c05')
        assert workspace.state()['tiles']['r03c05']==workspace.original_state()['tiles']['r03c05']
        run('rollback','--release',example)
        assert workspace.state()['tiles']['r03c05']['version']=='shape-01'
        run('rollback','--release',original)
        assert workspace.state()['tiles']['r03c05']['version']=='original'
        success=True
    finally:
        target=example if success and args.leave_example else initial
        if target:run('rollback','--release',target)
    save(workspace.root/'reports/lifecycle.json',{'status':'passed','initialRelease':initial,'finalRelease':load(workspace.root/'current.json')['release'],
        'unrelatedSourcesUnchanged':True,'sectionRollbackVerified':True,'releaseRollbackVerified':True,'commands':commands})


if __name__=='__main__':main()
