from utils import (
    get_invitation_link,
    get_introduction_link,
    get_obj_proper_name,
    get_icons,
)


def base_modifier(base_bubble):
    # add universal settings
    pass


def invitation_modifier(base_bubble, matching_row):
    get_invitation_link()
    get_introduction_link()
    get_obj_proper_name()
    get_icons()

    return base_bubble


BUBBLE_MODIFIER = {
    'invitation': invitation_modifier,
    # Add other bubble modifiers as needed
}
