from beartype import BeartypeConf
from beartype.claw import beartype_this_package

beartype_this_package(conf=BeartypeConf(is_color=False))

from pocket_tts.models.tts_model import TTSModel  # noqa: E402
from pocket_tts.utils.utils import set_cache_directory, get_cache_directory  # noqa: E402

# Public methods:
# TTSModel.device
# TTSModel.sample_rate
# TTSModel.load_model(cache_dir=None) - Pass custom cache directory for model downloads
# TTSModel.generate_audio
# TTSModel.generate_audio_stream
# TTSModel.get_state_for_audio_prompt
# set_cache_directory(path) - Set global cache directory before loading model
# get_cache_directory() - Get current cache directory

__all__ = ["TTSModel", "set_cache_directory", "get_cache_directory"]
