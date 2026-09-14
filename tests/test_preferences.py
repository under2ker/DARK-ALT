from dark_alt.schemas import PreferencesRequest

def test_preferences_are_normalized_and_deduplicated():
    value=PreferencesRequest(preferred_moods=[' dark ','DARK','cinematic'],preferred_tones=['dark','DARK'],preferred_resolutions=['4k','4K'],default_download_preset='FHD')
    assert value.preferred_moods==['DARK','CINEMATIC']
    assert value.preferred_tones==['DARK']
    assert value.preferred_resolutions==['4K']
