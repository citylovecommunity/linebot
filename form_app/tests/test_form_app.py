from app import get_proper_name, app


def test_get_proper_name():
    with app.app_context():
        # Assuming this is a valid object_id in your database

        assert get_proper_name({'object_id': 2}) == '林小姐'
        assert get_proper_name({'object_id': 10}) == '李先生'
        assert get_proper_name({'object_id': 152}) == '吳先生'
