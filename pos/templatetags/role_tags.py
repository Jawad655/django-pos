from django import template


register = template.Library()


@register.filter
def has_role(user, role):
    if not user or not user.is_authenticated:
        return False

    return getattr(user, "role", None) == role


@register.simple_tag
def is_manager(user):
    if not user or not user.is_authenticated:
        return False

    return getattr(user, "role", None) == "manager"