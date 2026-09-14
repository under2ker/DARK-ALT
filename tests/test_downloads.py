from io import BytesIO
from PIL import Image
from dark_alt.download_service import render_variant, resolve_size

def source_bytes():
    buffer=BytesIO(); Image.new('RGB',(800,600),(20,40,80)).save(buffer,'JPEG'); return buffer.getvalue()

def test_all_download_modes_render_requested_canvas():
    for mode in ('fit','fill','crop','center','stretch','blur_background'):
        data,mime,extension=render_variant(source_bytes(),(320,180),mode,'JPEG',85)
        with Image.open(BytesIO(data)) as image: assert image.size==(320,180)
        assert mime=='image/jpeg' and extension=='jpg'

def test_resize_does_not_upscale_by_default():
    assert resolve_size((800,600),'FHD',None,None,False)==(800,450)
