"""Independent PNG checks and diagnostic appearance measurements; no repainting."""
import numpy as np
from PIL import Image, ImageDraw
from .core import digest, load

Image.MAX_IMAGE_PIXELS=150_000_000


def appearance(path,rect):
    with Image.open(path) as image:
        hsv=np.asarray(image.convert('HSV').crop(rect)).astype(float)/255
        gray=np.asarray(image.convert('L').crop(rect)).astype(float)/255
    return {'saturation':float(hsv[:,:,1].mean()),'brightness':float(hsv[:,:,2].mean()),
        'detailContrast':float(np.abs(np.diff(gray,axis=1)).mean())}


def candidate_quality(workspace,folder,request):
    base=Image.open(workspace.path(request['base']['path'])).convert('RGBA')
    edited=Image.open(folder/'image.png').convert('RGBA');raw=Image.open(folder/'raw.png').convert('RGBA')
    if base.size!=edited.size or edited.size!=raw.size:raise ValueError('Native dimensions changed')
    a,b,c,d=request['editRect'];outside=np.ones((base.height,base.width),dtype=bool);outside[b:d,a:c]=False
    delta=np.abs(np.asarray(base).astype(np.int16)-np.asarray(edited).astype(np.int16))
    outside_max=int(delta[outside].max()) if outside.any() else 0
    if outside_max:raise ValueError('Pixels outside the requested edit region changed')
    inner=(a+16,b+16,c-16,d-16)
    inside_delta=int(np.abs(np.asarray(raw.crop(inner)).astype(np.int16)-np.asarray(edited.crop(inner)).astype(np.int16)).max())
    if inside_delta:raise ValueError('Generated interior was recolored or resampled')
    binding=next(i for i in workspace.baseline()['items'] if i['id']==request['tile'])
    original=appearance(workspace.path('baseline/'+binding['image']),request['editRect'])
    target=appearance(workspace.path(request['base']['path']),request['editRect'])
    new=appearance(folder/'image.png',request['editRect'])
    saturation=new['saturation']-original['saturation'];brightness=new['brightness']-original['brightness']
    detail=new['detailContrast']/max(original['detailContrast'],.00001)
    warnings=[]
    if abs(saturation)>.08:warnings.append('Saturation differs by more than eight percentage points')
    if abs(brightness)>.08:warnings.append('Brightness differs by more than eight percentage points')
    if not .8<=detail<=1.25:warnings.append('Detail contrast differs materially')
    return {'outsideEditMaxChannelDifference':outside_max,'generatedInteriorMaxChannelDifference':inside_delta,
        'original':original,'editTarget':target,'candidate':new,'saturationDifference':saturation,'brightnessDifference':brightness,
        'detailRatio':detail,'warnings':warnings,'note':'Diagnostics only; visual comparison of palette, structure and seams is required.'}


def verify_release(workspace,folder,state,assembly,config):
    master=Image.open(folder/'master.png').convert('RGBA');width,height=master.size
    plan=workspace.plan()
    if list(master.size)!=plan['imageSize']:raise ValueError('Master extent changed')
    channels=0;maximum=0;hashes={}
    for key in config['tileKeys']:
        path=folder/f'tiles/{key}.png';tile=Image.open(path).convert('RGBA')
        if tile.size!=(256,256):raise ValueError('Delivery dimensions changed')
        hashes[key]=digest(path);z,x,y=map(int,key.split('/'))
        if z:continue
        w,h=min(256,width-x*256),min(256,height-y*256)
        a=np.asarray(tile)[:h,:w].astype(np.int16)
        b=np.asarray(master.crop((x*256,y*256,x*256+w,y*256+h))).astype(np.int16)
        maximum=max(maximum,int(np.abs(a-b).max()));channels+=a.size
        if maximum:raise ValueError('Native delivery differs from master')
    sources=[]
    tiles={i['id']:i for i in plan['tiles']}
    for id,item in state['tiles'].items():
        ox,oy=tiles[id]['renderOrigin'];box=(560,560,624,624)
        if ox+560<0 or oy+560<0 or ox+624>width or oy+624>height:continue
        a=np.asarray(Image.open(workspace.path(item['path'])).convert('RGBA').crop(box)).astype(np.int16)
        b=np.asarray(master.crop((ox+560,oy+560,ox+624,oy+624))).astype(np.int16)
        difference=int(np.abs(a-b).max());sources.append({'id':id,'maxChannelDifference':difference})
        if difference:raise ValueError('Native source core changed: '+id)
    for region in assembly['protectedRegions']:
        a,b,c,d=map(int,region['rect']);ox,oy=tiles[region['owner']]['renderOrigin']
        source=Image.open(workspace.path(state['tiles'][region['owner']]['path'])).convert('RGBA')
        expected=np.asarray(source.crop((a-ox,b-oy,c-ox,d-oy))).astype(np.int16)
        if np.any(expected!=np.asarray(master.crop((a,b,c,d))).astype(np.int16)):raise ValueError('Protected landmark changed: '+region['id'])
    city=Image.new('L',(width,height),0);draw=ImageDraw.Draw(city);west,_,_,north=plan['bounds'];scale=plan['scale']
    for ring in plan['cityOutline']:
        pixels=[((x-west)*scale,(north-y)*scale) for x,y in ring]
        if any(x<0 or y<0 or x>width or y>height for x,y in pixels):raise ValueError('City boundary outside extent')
        draw.polygon(pixels,fill=255)
    missing=int(np.count_nonzero((np.asarray(city)>0)&(np.asarray(master.getchannel('A'))==0)))
    if missing:raise ValueError('Unpainted city pixels: '+str(missing))
    quality={'masterSha256':digest(folder/'master.png'),'maxChannelDifference':maximum,'channelsCompared':channels,
        'format':'lossless PNG','sourceResampleFactor':1,'sourceChecks':sources,'sourceSampleSize':[64,64],
        'unpaintedCityPixels':missing,'originalCount':len(state['tiles']),'protectedRegions':len(assembly['protectedRegions']),
        'completeBoundaryInside':True}
    return quality,hashes


def compare_masters(a,b):
    left=Image.open(a).convert('RGBA');right=Image.open(b).convert('RGBA')
    if left.size!=right.size:raise ValueError('Master dimensions differ')
    maximum=0;channels=0
    for y in range(0,left.height,256):
        box=(0,y,left.width,min(left.height,y+256))
        x=np.asarray(left.crop(box)).astype(np.int16);z=np.asarray(right.crop(box)).astype(np.int16)
        maximum=max(maximum,int(np.abs(x-z).max()));channels+=x.size
    return {'maxChannelDifference':maximum,'channelsCompared':channels}


def verify_local_change(original,edited,rect):
    left=Image.open(original).convert('RGBA');right=Image.open(edited).convert('RGBA')
    if left.size!=right.size:raise ValueError('Master dimensions changed')
    a,b,c,d=rect;outside_max=0;changed=0
    for y in range(0,left.height,128):
        end=min(left.height,y+128);box=(0,y,left.width,end)
        delta=np.abs(np.asarray(left.crop(box)).astype(np.int16)-np.asarray(right.crop(box)).astype(np.int16))
        mask=np.ones(delta.shape[:2],dtype=bool)
        if y<d and end>b:mask[max(0,b-y):min(end-y,d-y),a:c]=False
        outside_max=max(outside_max,int(delta[mask].max()) if mask.any() else 0)
        changed+=int(np.count_nonzero(np.any(delta>0,axis=2)))
    if outside_max:raise ValueError('Replacement changed master pixels outside its edit footprint')
    if not changed:raise ValueError('Replacement made no visible change')
    return {'outsideEditMaxChannelDifference':outside_max,'changedPixels':changed,'globalEditRect':rect}
