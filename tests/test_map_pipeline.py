"""Lifecycle safeguards and regressions that matter for actual map replacement."""
import shutil
from pathlib import Path
import pytest
from PIL import Image
from src.map_pipeline.core import Workspace,digest,identity,load,save
from src.map_pipeline.quality import candidate_quality


@pytest.fixture
def workspace(tmp_path):
    root=tmp_path/'atlas';(root/'baseline/images').mkdir(parents=True)
    Image.new('RGB',(1254,1254),(80,120,45)).save(root/'baseline/images/r01c01.png')
    (root/'baseline/prompts').mkdir();(root/'baseline/prompts/r01c01.md').write_text('original prompt')
    (root/'base-prompt.md').write_text('Binding original appearance.')
    plan={'tiles':[{'id':'r01c01','renderOrigin':[0,0]}],'landmarks':[]};save(root/'plan.json',plan)
    image='images/r01c01.png'
    item={'id':'r01c01','image':image,'sha256':digest(root/'baseline'/image),'prompt':'prompts/r01c01.md',
        'promptSha256':digest(root/'baseline/prompts/r01c01.md'),'references':[],
        'guide':{'path':image,'sha256':digest(root/'baseline'/image)},'targets':{'path':image,'sha256':digest(root/'baseline'/image)},'input':{'path':image,'sha256':digest(root/'baseline'/image)}}
    save(root/'baseline/manifest.json',{'items':[item],'nativeSize':[1254,1254],'imageSize':[1254,1254],
        'planSha256':digest(root/'plan.json'),'basePromptSha256':digest(root/'base-prompt.md')})
    return Workspace(root)


def imported(workspace,version='one',warnings=None):
    workspace.prepare('r01c01',version,'Change a small courtyard')
    folder=workspace.candidate('r01c01',version);request=load(folder/'request.json')
    for name in ['raw.png','image.png']:shutil.copyfile(workspace.path(request['base']['path']),folder/name)
    save(folder/'quality.json',{'warnings':warnings or []})
    request.update(rawSha256=digest(folder/'raw.png'),imageSha256=digest(folder/'image.png'),qualitySha256=digest(folder/'quality.json'))
    save(folder/'request.json',request)
    return folder


@pytest.mark.parametrize('path',['../../web/app.js','/absolute','C:/outside','..\\outside'])
def test_paths_cannot_escape_workspace(workspace,path):
    with pytest.raises(ValueError):workspace.path(path)


def test_preparation_preserves_original_and_rejects_overwrite(workspace):
    before=digest(workspace.path('baseline/images/r01c01.png'))
    workspace.prepare('r01c01','one','Change courtyard')
    with pytest.raises(ValueError,match='already exists'):workspace.prepare('r01c01','one','Another change')
    assert before==digest(workspace.path('baseline/images/r01c01.png'))


def test_unreviewed_candidate_cannot_be_published(workspace):
    imported(workspace);state=workspace.proposed_state('r01c01','one')
    with pytest.raises(ValueError,match='Visual review'):workspace.validate_state(state,require_review=True)
    workspace.review('r01c01','one','accept','Palette and surrounding streets visually match.')
    workspace.validate_state(state,require_review=True)


def test_provenance_change_invalidates_an_accepted_candidate(workspace):
    folder=imported(workspace);workspace.review('r01c01','one','accept','Looks consistent')
    (folder/'prompt.md').write_text('Different prompt after generation')
    with pytest.raises(ValueError,match='provenance'):workspace.proposed_state('r01c01','one')


def test_warning_cannot_be_silently_accepted(workspace):
    imported(workspace,warnings=['Palette drift'])
    with pytest.raises(ValueError,match='warnings'):workspace.review('r01c01','one','accept','Looks fine')
    workspace.review('r01c01','one','reject','Pale, unlike the original.')
    with pytest.raises(ValueError,match='Visual review'):workspace.validate_state(workspace.proposed_state('r01c01','one'),require_review=True)


def test_stale_candidate_does_not_replace_newer_work(workspace,monkeypatch):
    imported(workspace);current=workspace.original_state();current['tiles']['r01c01']['sha256']='newer-image'
    monkeypatch.setattr(workspace,'state',lambda:current)
    with pytest.raises(ValueError,match='Stale'):workspace.proposed_state('r01c01','one')


def test_wrong_native_size_is_rejected_without_rescaling(workspace,tmp_path):
    workspace.prepare('r01c01','one','Change courtyard');image=tmp_path/'small.png';Image.new('RGB',(1024,1024)).save(image)
    with pytest.raises(ValueError,match='native size'):workspace.import_image('r01c01','one',image)
    assert not (workspace.candidate('r01c01','one')/'image.png').exists()


def test_quality_detects_pale_flat_replacement(workspace):
    folder=imported(workspace);request=load(folder/'request.json');base=Image.open(workspace.path(request['base']['path'])).convert('RGBA')
    raw=Image.new('RGBA',base.size,(242,239,230,255));raw.save(folder/'raw.png')
    base.paste(raw.crop(request['editRect']),request['editRect']);base.save(folder/'image.png')
    report=candidate_quality(workspace,folder,request)
    assert report['outsideEditMaxChannelDifference']==0
    assert report['generatedInteriorMaxChannelDifference']==0
    assert any('Saturation' in warning for warning in report['warnings'])


def test_even_one_changed_context_pixel_is_rejected(workspace):
    folder=imported(workspace);request=load(folder/'request.json');image=Image.open(folder/'image.png').convert('RGBA')
    image.putpixel((0,0),(81,120,45,255));image.save(folder/'image.png')
    with pytest.raises(ValueError,match='outside'):candidate_quality(workspace,folder,request)


def test_two_writers_cannot_lose_each_others_state(workspace):
    with workspace.lock():
        with pytest.raises(RuntimeError,match='Another map command'):
            with workspace.lock():pass


def test_selected_sources_survive_removal_of_derived_release_cache(workspace):
    state=workspace.original_state();key=identity(state)
    save(workspace.root/f'states/{key}.json',state)
    save(workspace.root/'current.json',{'release':'not-built-here','stateSha256':key})
    assert workspace.state()==state
    assert workspace.inspect()['originalSections']==1


def test_active_review_cannot_be_revoked_before_rollback(workspace,monkeypatch):
    imported(workspace);workspace.review('r01c01','one','accept','Looks consistent')
    state=workspace.proposed_state('r01c01','one');monkeypatch.setattr(workspace,'state',lambda:state)
    with pytest.raises(ValueError,match='Roll back'):workspace.review('r01c01','one','reject','Reconsidered')


def test_palette_drift_is_measured_against_original_not_previous_edit(workspace):
    folder=imported(workspace);request=load(folder/'request.json')
    previous=workspace.root/'previous.png';Image.new('RGBA',(1254,1254),(145,170,120,255)).save(previous)
    request['base']={'path':'previous.png','sha256':digest(previous)}
    raw=Image.new('RGBA',(1254,1254),(155,175,135,255));raw.save(folder/'raw.png')
    image=Image.open(previous);image.paste(raw.crop(request['editRect']),request['editRect']);image.save(folder/'image.png')
    report=candidate_quality(workspace,folder,request)
    assert abs(report['candidate']['saturation']-report['editTarget']['saturation'])<.08
    assert abs(report['saturationDifference'])>.08
    assert any('Saturation' in warning for warning in report['warnings'])


def cloud_frame(workspace, tmp_path, version='clouds'):
    from src.map_pipeline.frame import folder_for, import_frame
    folder=folder_for(workspace,version);folder.mkdir(parents=True)
    (folder/'prompt.md').write_text('Paint warm ivory clouds, in the original atlas style.')
    source=tmp_path/(version+'.png');Image.new('RGB',(512,512),(242,239,230)).save(source)
    return import_frame(workspace,version,source,references=['baseline/images/r01c01.png'])


def test_cloud_frame_cannot_be_published_without_visual_review(workspace,tmp_path):
    from src.map_pipeline.frame import review_frame
    item=cloud_frame(workspace,tmp_path);state=workspace.original_state();state['frame']=item
    with pytest.raises(ValueError,match='Visual review'):workspace.validate_state(state,require_review=True)
    review_frame(workspace,'clouds','accept','Cloud palette and full rectangle visually inspected.')
    workspace.validate_state(state,require_review=True)
    assert 'frame' not in workspace.original_state()


@pytest.mark.parametrize('name',['raw.png','recipe.json','prompt.md'])
def test_accepted_cloud_frame_detects_modified_artwork_or_recipe(workspace,tmp_path,name):
    from src.map_pipeline.frame import check_frame,folder_for,review_frame
    item=cloud_frame(workspace,tmp_path);review_frame(workspace,'clouds','accept','Reviewed the complete map.')
    with (folder_for(workspace,'clouds')/name).open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='provenance'):check_frame(workspace,item,require_review=True)


def test_cloud_mask_preserves_city_islands_and_outlying_landmarks(workspace,tmp_path):
    import numpy as np
    from src.map_pipeline.frame import city_mask,make_mask
    item=cloud_frame(workspace,tmp_path)
    plan=workspace.plan()
    plan.update(imageSize=[1254,1254],bounds=[0,0,1254,1254],scale=1,
                cityOutline=[[[300,300],[950,300],[950,950],[300,950]],
                             [[90,1000],[120,1000],[120,1030],[90,1030]]],
                landmarks=[{'protectedRect':[1000,1100,1050,1150]}])
    save(workspace.root/'plan.json',plan)
    output=tmp_path/'mask.png';make_mask(workspace,item,output)
    mask=np.asarray(Image.open(output));city=np.asarray(city_mask(plan))>0
    assert np.max(mask[city])==0
    assert np.max(mask[1100:1150,1000:1050])==0
    assert mask[0,0]==255
    assert np.array_equal(mask,np.asarray(Image.open(tmp_path/'cloud-alpha.png').getchannel('A')))


def test_cloud_verification_rejects_changed_city_or_transparent_rectangle(tmp_path):
    from src.map_pipeline.frame import verify_frame
    plan={'imageSize':[64,64],'bounds':[0,0,64,64],'scale':1,
          'cityOutline':[[[20,20],[40,20],[40,40],[20,40]]]}
    ground=Image.new('RGBA',(64,64),(80,120,45,255));ground.save(tmp_path/'ground.png')
    ground.save(tmp_path/'master.png');Image.new('L',(64,64),0).save(tmp_path/'cloud-mask.png')
    assert verify_frame(tmp_path,plan)['rectangularOpaque']
    changed=ground.copy();changed.putpixel((30,30),(81,120,45,255));changed.save(tmp_path/'master.png')
    with pytest.raises(ValueError,match='city pixels'):verify_frame(tmp_path,plan)
    changed=ground.copy();changed.putpixel((0,0),(80,120,45,0));changed.save(tmp_path/'master.png')
    with pytest.raises(ValueError,match='transparent'):verify_frame(tmp_path,plan)


def test_activation_rejects_a_different_inspected_release(workspace,tmp_path,monkeypatch):
    import sys
    from src.map_pipeline import __main__ as cli,render
    other=workspace.original_state();other['tiles']['r01c01']['version']='another-selection'
    release=tmp_path/'release';release.mkdir();save(release/'state.json',other)
    monkeypatch.setattr(cli,'Workspace',lambda:workspace)
    monkeypatch.setattr(render,'validate_release',lambda *args:release)
    monkeypatch.setattr(sys,'argv',['map_pipeline','activate-set','--release','inspected'])
    with pytest.raises(ValueError,match='does not match'):cli.main()
    assert not (workspace.root/'current.json').exists()
