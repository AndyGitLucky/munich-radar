from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.map_pipeline.core import digest,save
from src.map_pipeline.public import install_bundle


def package(tmp_path,name='releases/approved/tiles/0/0/0.png',data=b'native pixels',expected=None):
    root=tmp_path/'project';(root/'atlas').mkdir(parents=True)
    archive=tmp_path/'approved.zip'
    with ZipFile(archive,'w') as output:
        output.writestr(name,data)
        output.writestr('catalog.json',json.dumps({'release':'approved','baseline':'original',
                         'files':{name:expected or sha256(data).hexdigest()}}))
    save(root/'atlas/distribution.json',{'release':'approved','baseline':'original','sha256':digest(archive)})
    return root,archive


def test_public_package_preserves_delivered_bytes(tmp_path):
    root,archive=package(tmp_path)
    destination=tmp_path/'public'
    install_bundle(root,destination,archive)
    assert (destination/'releases/approved/tiles/0/0/0.png').read_bytes()==b'native pixels'


def test_public_package_detects_wrong_native_asset(tmp_path):
    root,archive=package(tmp_path,expected='0'*64)
    with pytest.raises(ValueError,match='file checksum mismatch'):
        install_bundle(root,tmp_path/'public',archive)


def test_public_package_detects_a_changed_archive(tmp_path):
    root,archive=package(tmp_path)
    with archive.open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError,match='archive checksum mismatch'):
        install_bundle(root,tmp_path/'public',archive)


@pytest.mark.parametrize('name',['../outside','/outside','C:/outside','folder\\outside'])
def test_public_package_rejects_paths_outside_destination(tmp_path,name):
    root,archive=package(tmp_path,name)
    with pytest.raises(ValueError,match='Unsafe'):
        install_bundle(root,tmp_path/'public',archive)
