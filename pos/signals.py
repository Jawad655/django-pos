from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission


@receiver(post_migrate)
def create_user_groups(sender, **kwargs):

    if sender.name != "pos":
        return

    # =====================================================
    # CREATE USER ROLES
    # =====================================================

    manager_group, _ = Group.objects.get_or_create(
        name="Manager"
    )

    cashier_group, _ = Group.objects.get_or_create(
        name="Cashier"
    )

    kitchen_group, _ = Group.objects.get_or_create(
        name="Kitchen Staff"
    )

    # =====================================================
    # POS APP PERMISSIONS
    # =====================================================

    permissions = Permission.objects.filter(
        content_type__app_label="pos"
    )

    # =====================================================
    # MANAGER
    # Full POS application access
    # =====================================================

    manager_group.permissions.set(
        permissions
    )

    # =====================================================
    # CASHIER
    # POS + Orders + Billing
    # =====================================================

    cashier_permissions = permissions.filter(
        content_type__model__in=[
            "order",
            "orderitem",
            "table",
        ]
    )

    cashier_group.permissions.set(
        cashier_permissions
    )

    # =====================================================
    # KITCHEN STAFF
    # Orders + KOT related access
    # =====================================================

    kitchen_permissions = permissions.filter(
        content_type__model__in=[
            "order",
            "orderitem",
        ]
    )

    kitchen_group.permissions.set(
        kitchen_permissions
    )