import os
from typing import Type

from PIL import Image

from tabs.cah_tab import CustomHeroTab
from tabs.generic_tab import GenericTab
from tabs.image_tab import ImageTab
from tabs.map_tab import MapTab
from tabs.text_tab import TextTab
from tabs.media_tab import MULTIE_MEDIA_TYPES, MediaTab
from tabs.w3d_tab import W3DTab

TAB_TYPES = {
    (".bse", ".map"): MapTab,
    MULTIE_MEDIA_TYPES: MediaTab,
    (".cah",): CustomHeroTab,
    (".w3d",): W3DTab,
    tuple(Image.registered_extensions().keys()): ImageTab,
}


def get_tab_from_file_type(name: str) -> Type[GenericTab]:
    file_type = os.path.splitext(name)[1].lower()

    for key, value in TAB_TYPES.items():
        if file_type in key:
            return value

    return TextTab
