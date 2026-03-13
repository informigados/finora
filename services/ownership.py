from database.db import db


def get_owned_or_none(model, resource_id, user_id):
    resource = db.session.get(model, resource_id)
    if not resource or getattr(resource, 'user_id', None) != user_id:
        return None
    return resource
