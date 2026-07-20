from database.db import db


def get_owned_or_none(model, resource_id, user_id):
    if resource_id is None:
        return None
    resource = db.session.get(model, resource_id)
    if not resource or getattr(resource, 'user_id', None) != user_id:
        return None
    return resource
