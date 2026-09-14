from dark_alt.models import Wallpaper
from dark_alt.semantic import classify

def wallpaper(**kwargs):
    data=dict(id=1,slug='test',title='Dark Cyberpunk Space City',source='test',source_url='https://example.com',image_url='https://example.com/a.jpg',thumbnail_url='https://example.com/a.jpg',width=3840,height=2160,ratio='16:9',orientation='landscape',resolution='4K',tone='DARK',tags=['cyberpunk','space'],categories=['TECHNOLOGY'],quality_score=90,provider_key='test',provider_external_id='1',dominant_color='#071633',brightness=.12)
    data.update(kwargs); return Wallpaper(**data)

def test_semantic_classification_assigns_scene_style_and_moods():
    profile=classify(wallpaper())
    assert profile['scene']=='technology'
    assert profile['style']=='futuristic'
    assert 'dark' in profile['moods'] and 'futuristic' in profile['moods']
