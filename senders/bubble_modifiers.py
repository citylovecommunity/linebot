from utils import (
    get_invitation_link,
    get_introduction_link,
    get_obj_proper_name,
    get_icons,
)
from config import BUBBLE_HERO_IMAGE_URL


def base_modifier(base_bubble):
    # add universal settings
    base_bubble['hero']['url'] = BUBBLE_HERO_IMAGE_URL
    return base_bubble


def invitation_modifier(conn, base_bubble, matching_row):
    base_bubble = base_modifier(base_bubble)
    form_app_link = get_invitation_link(matching_row)
    intro_link = get_introduction_link(conn, matching_row)
    obj_proper_name = get_obj_proper_name(conn, matching_row)
    # get_icons()

    base_bubble["body"]["contents"][3]["contents"][0]["contents"][1]["text"] = obj_proper_name
    base_bubble["footer"]["contents"][0]["action"]["uri"] = intro_link
    base_bubble["footer"]["contents"][1]["action"]["uri"] = form_app_link
    return base_bubble


BUBBLE_MODIFIER = {
    'invitation': invitation_modifier,

    # Add other bubble modifiers as needed
}
