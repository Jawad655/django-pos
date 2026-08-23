from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from decimal import Decimal, InvalidOperation
from django.db import transaction
import json

from .models import (
    Restaurant,
    Branch,
    Category,
    MenuItem,
    Table,
    Order,
    OrderItem,
    Ingredient,
    StockIn,
    StockUsage,
    MenuItemIngredient,
    UserBranch,
)


# =========================================================
# BILLING CONSTANTS
# =========================================================

TAX_RATE = Decimal("0.05")
FIXED_SERVICE_CHARGE = Decimal("400.00")


# =========================================================
# SMALL HELPERS
# =========================================================

def decimal_value(value, default="0"):
    try:
        return Decimal(str(value if value not in [None, ""] else default))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid numeric value.")


def get_current_branch(user):

    if not user.is_authenticated:
        return None

    user_branch = (
        UserBranch.objects
        .select_related("branch")
        .filter(
            user=user,
            branch__active=True
        )
        .first()
    )

    if not user_branch:
        return None

    return user_branch.branch


# =========================================================
# LOGIN
# =========================================================

def login_view(request):

    if request.user.is_authenticated:
        return redirect("pos_home")

    error = ""

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if not username or not password:

            error = "Username and password are required."

        else:

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                if user.is_active:

                    login(
                        request,
                        user
                    )

                    next_url = request.GET.get("next")

                    if next_url:
                        return redirect(next_url)

                    return redirect("pos_home")

                error = "This account is disabled."

            else:

                error = "Invalid username or password."

    return render(
        request,
        "pos/login.html",
        {
            "error": error
        }
    )


# =========================================================
# LOGOUT
# =========================================================

def logout_view(request):

    logout(request)

    return redirect("login")


# =========================================================
# ROLE HELPERS
# =========================================================

def is_manager(user):

    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(
                name="Manager"
            ).exists()
        )
    )


def is_cashier(user):

    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(
                name__in=[
                    "Manager",
                    "Cashier",
                ]
            ).exists()
        )
    )


def is_kitchen_staff(user):

    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(
                name__in=[
                    "Manager",
                    "Cashier",
                    "Kitchen Staff",
                ]
            ).exists()
        )
    )


# =========================================================
# MANAGER ACCESS
# =========================================================

def manager_required(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not is_manager(request.user):
            raise PermissionDenied

        return view_func(
            request,
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# ORDER STAFF ACCESS
# =========================================================

def order_staff_required(view_func):

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not is_kitchen_staff(request.user):
            raise PermissionDenied

        return view_func(
            request,
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# POS HOME
# =========================================================

@login_required(login_url="login")
def pos_home(request):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    categories = (
        Category.objects
        .filter(branch=branch)
        .order_by("name")
    )

    menu_items = (
        MenuItem.objects
        .filter(
            branch=branch,
            available=True
        )
        .select_related("category")
        .order_by("name")
    )

    tables = (
        Table.objects
        .filter(branch=branch)
        .order_by("number")
    )

    orders = (
        Order.objects
        .filter(branch=branch)
        .prefetch_related("items")
        .select_related("table")
        .order_by("-created_at")
    )

    return render(
        request,
        "pos/pos.html",
        {
            "categories": categories,
            "menu_items": menu_items,
            "tables": tables,
            "orders": orders,
            "branch": branch,
        }
    )


# =========================================================
# ADD TABLE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_table(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        data = json.loads(request.body)

        number = data.get("number")
        capacity = data.get("capacity", 4)

        if number in [None, ""]:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Table number is required."
                },
                status=400
            )

        try:
            number = int(number)

            if number <= 0:
                raise ValueError

        except (ValueError, TypeError):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid table number."
                },
                status=400
            )

        try:
            capacity = int(capacity)

            if capacity <= 0:
                raise ValueError

        except (ValueError, TypeError):
            capacity = 4

        if Table.objects.filter(
            branch=branch,
            number=number
        ).exists():

            return JsonResponse(
                {
                    "success": False,
                    "message": "This table number already exists in this branch."
                },
                status=400
            )

        table = Table.objects.create(
            branch=branch,
            number=number,
            capacity=capacity,
            is_occupied=False
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Table added successfully.",
                "table": {
                    "id": table.id,
                    "number": table.number,
                    "capacity": table.capacity,
                    "is_occupied": table.is_occupied,
                }
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid data."
            },
            status=400
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )


# =========================================================
# EDIT TABLE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_table(request, table_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        table = Table.objects.get(
            id=table_id,
            branch=branch
        )

    except Table.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Table not found."
            },
            status=404
        )

    if table.is_occupied:

        return JsonResponse(
            {
                "success": False,
                "message": "Occupied table cannot be edited."
            },
            status=400
        )

    try:

        data = json.loads(request.body)

        number = data.get("number")
        capacity = data.get(
            "capacity",
            table.capacity
        )

        if number in [None, ""]:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Table number is required."
                },
                status=400
            )

        try:

            number = int(number)

            if number <= 0:
                raise ValueError

        except (ValueError, TypeError):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid table number."
                },
                status=400
            )

        if Table.objects.filter(
            branch=branch,
            number=number
        ).exclude(
            id=table.id
        ).exists():

            return JsonResponse(
                {
                    "success": False,
                    "message": "This table number already exists in this branch."
                },
                status=400
            )

        try:

            capacity = int(capacity)

            if capacity <= 0:
                raise ValueError

        except (ValueError, TypeError):

            capacity = table.capacity

        table.number = number
        table.capacity = capacity

        table.save(
            update_fields=[
                "number",
                "capacity"
            ]
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Table updated successfully.",
                "table": {
                    "id": table.id,
                    "number": table.number,
                    "capacity": table.capacity,
                    "is_occupied": table.is_occupied,
                }
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid data."
            },
            status=400
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )


# =========================================================
# DELETE TABLE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_table(request, table_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        table = Table.objects.get(
            id=table_id,
            branch=branch
        )

    except Table.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Table not found."
            },
            status=404
        )

    if table.is_occupied:

        return JsonResponse(
            {
                "success": False,
                "message": "Occupied table cannot be deleted."
            },
            status=400
        )

    if Order.objects.filter(
        branch=branch,
        table=table
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This table has order history and cannot be deleted."
            },
            status=400
        )

    table.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Table deleted successfully."
        }
    )


# =========================================================
# DASHBOARD
# =========================================================

@login_required(login_url="login")
@manager_required
def dashboard(request):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    orders = Order.objects.filter(
        branch=branch
    )

    total_orders = orders.count()

    completed_orders = orders.filter(
        status="completed"
    ).count()

    cancelled_orders = orders.filter(
        status="cancelled"
    ).count()

    pending_orders = orders.filter(
        status="pending"
    ).count()

    total_sales = (
        orders
        .filter(status="completed")
        .aggregate(total=Sum("total"))
        .get("total")
        or Decimal("0")
    )

    today = timezone.localdate()

    today_orders = orders.filter(
        created_at__date=today
    )

    today_sales = (
        today_orders
        .filter(status="completed")
        .aggregate(total=Sum("total"))
        .get("total")
        or Decimal("0")
    )

    total_menu_items = MenuItem.objects.filter(
        branch=branch
    ).count()

    total_categories = Category.objects.filter(
        branch=branch
    ).count()

    total_tables = Table.objects.filter(
        branch=branch
    ).count()

    occupied_tables = Table.objects.filter(
        branch=branch,
        is_occupied=True
    ).count()

    low_stock_items = []

    ingredients = Ingredient.objects.filter(
        branch=branch,
        active=True
    )

    for ingredient in ingredients:

        if (
            ingredient.is_low_stock
            or ingredient.is_out_of_stock
        ):
            low_stock_items.append(ingredient)

    return render(
        request,
        "pos/dashboard.html",
        {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "cancelled_orders": cancelled_orders,
            "pending_orders": pending_orders,
            "total_sales": total_sales,
            "today_sales": today_sales,
            "today_orders": today_orders.count(),
            "total_menu_items": total_menu_items,
            "total_categories": total_categories,
            "total_tables": total_tables,
            "occupied_tables": occupied_tables,
            "low_stock_items": low_stock_items,
            "branch": branch,
        }
    )


# =========================================================
# MENU
# =========================================================

@login_required(login_url="login")
@manager_required
def menu(request):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    categories = (
        Category.objects
        .filter(branch=branch)
        .prefetch_related("items")
        .order_by("name")
    )

    ingredients = (
        Ingredient.objects
        .filter(
            branch=branch,
            active=True
        )
        .order_by("name")
    )

    menu_items = (
        MenuItem.objects
        .filter(branch=branch)
        .select_related("category")
        .prefetch_related("ingredients__ingredient")
        .order_by("name")
    )

    return render(
        request,
        "pos/menu.html",
        {
            "categories": categories,
            "ingredients": ingredients,
            "menu_items": menu_items,
            "branch": branch,
        }
    )


# =========================================================
# ADD CATEGORY
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_category(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Category name is required."
            },
            status=400
        )

    if Category.objects.filter(
        branch=branch,
        name__iexact=name
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This category already exists in this branch."
            },
            status=400
        )

    category = Category.objects.create(
        branch=branch,
        name=name
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Category added successfully.",
            "id": category.id,
            "name": category.name,
        }
    )


# =========================================================
# EDIT CATEGORY
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_category(request, category_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        category = Category.objects.get(
            id=category_id,
            branch=branch
        )

    except Category.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Category not found."
            },
            status=404
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Category name is required."
            },
            status=400
        )

    if Category.objects.filter(
        branch=branch,
        name__iexact=name
    ).exclude(
        id=category.id
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This category already exists in this branch."
            },
            status=400
        )

    category.name = name
    category.save(update_fields=["name"])

    return JsonResponse(
        {
            "success": True,
            "message": "Category updated successfully."
        }
    )


# =========================================================
# DELETE CATEGORY
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_category(request, category_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        category = Category.objects.get(
            id=category_id,
            branch=branch
        )

    except Category.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Category not found."
            },
            status=404
        )

    if category.items.exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This category contains menu items. "
                    "Delete or move the items first."
                )
            },
            status=400
        )

    category.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Category deleted successfully."
        }
    )


# =========================================================
# ADD MENU ITEM
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_menu_item(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    price = request.POST.get(
        "price",
        ""
    ).strip()

    category_id = request.POST.get(
        "category_id",
        ""
    ).strip()

    description = request.POST.get(
        "description",
        ""
    ).strip()

    available = (
        request.POST.get("available") == "on"
    )

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Item name is required."
            },
            status=400
        )

    if not price:

        return JsonResponse(
            {
                "success": False,
                "message": "Price is required."
            },
            status=400
        )

    if not category_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Please select a category."
            },
            status=400
        )

    try:

        category = Category.objects.get(
            id=category_id,
            branch=branch
        )

    except Category.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Category not found."
            },
            status=404
        )

    try:

        price = decimal_value(price)

        if price <= 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid price."
            },
            status=400
        )

    image = request.FILES.get("image")

    MenuItem.objects.create(
        branch=branch,
        category=category,
        name=name,
        description=description,
        price=price,
        image=image,
        available=available
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Menu item added successfully."
        }
    )


# =========================================================
# EDIT MENU ITEM
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_menu_item(request, item_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        item = MenuItem.objects.get(
            id=item_id,
            branch=branch
        )

    except MenuItem.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Menu item not found."
            },
            status=404
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    price = request.POST.get(
        "price",
        ""
    ).strip()

    category_id = request.POST.get(
        "category_id",
        ""
    ).strip()

    description = request.POST.get(
        "description",
        ""
    ).strip()

    available = (
        request.POST.get("available") == "on"
    )

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Item name is required."
            },
            status=400
        )

    if not price:

        return JsonResponse(
            {
                "success": False,
                "message": "Price is required."
            },
            status=400
        )

    if not category_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Please select a category."
            },
            status=400
        )

    try:

        category = Category.objects.get(
            id=category_id,
            branch=branch
        )

    except Category.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Category not found."
            },
            status=404
        )

    try:

        price = decimal_value(price)

        if price <= 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid price."
            },
            status=400
        )

    item.name = name
    item.price = price
    item.category = category
    item.description = description
    item.available = available

    image = request.FILES.get("image")

    if image:
        item.image = image

    item.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Menu item updated successfully."
        }
    )


# =========================================================
# DELETE MENU ITEM
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_menu_item(request, item_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        item = MenuItem.objects.get(
            id=item_id,
            branch=branch
        )

    except MenuItem.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Menu item not found."
            },
            status=404
        )

    if OrderItem.objects.filter(
        menu_item=item
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This item has already been used in an order. "
                    "Make it unavailable instead of deleting it."
                )
            },
            status=400
        )

    item.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Menu item deleted successfully."
        }
    )


# =========================================================
# CREATE POS ORDER
# =========================================================

@login_required(login_url="login")
@require_POST
def create_order(request):

    try:

        data = json.loads(request.body)

        branch = get_current_branch(request.user)

        if not branch:

            return JsonResponse(
                {
                    "success": False,
                    "message": "No branch assigned to this user."
                },
                status=400
            )

        table_id = data.get("table_id")
        items = data.get("items", [])

        order_type = data.get(
            "order_type",
            "dine_in"
        )

        payment_method = data.get(
            "payment_method",
            "cash"
        )

        try:

            discount = decimal_value(
                data.get("discount", "0")
            )

            paid_amount = decimal_value(
                data.get("paid_amount", "0")
            )

        except ValueError:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid payment or discount amount."
                },
                status=400
            )

        if order_type not in [
            "dine_in",
            "takeaway"
        ]:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid order type."
                },
                status=400
            )

        if payment_method not in [
            "cash",
            "card",
            "online"
        ]:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid payment method."
                },
                status=400
            )

        if not isinstance(items, list) or not items:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Cart is empty."
                },
                status=400
            )

        discount = max(discount, Decimal("0"))
        paid_amount = max(paid_amount, Decimal("0"))

        table = None

        if order_type == "dine_in" and not table_id:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please select a table."
                },
                status=400
            )

        if table_id:

            try:

                table = Table.objects.get(
                    id=table_id,
                    branch=branch
                )

            except Table.DoesNotExist:

                return JsonResponse(
                    {
                        "success": False,
                        "message": "Table not found."
                    },
                    status=404
                )

            if (
                order_type == "dine_in"
                and table.is_occupied
            ):

                return JsonResponse(
                    {
                        "success": False,
                        "message": "This table is already occupied."
                    },
                    status=400
                )

        with transaction.atomic():

            if table:

                table = (
                    Table.objects
                    .select_for_update()
                    .get(
                        id=table.id,
                        branch=branch
                    )
                )

                if (
                    order_type == "dine_in"
                    and table.is_occupied
                ):

                    raise ValueError(
                        "This table is already occupied."
                    )

            order = Order.objects.create(
                branch=branch,
                table=table,
                order_type=order_type,
                payment_method=payment_method,
                payment_status="unpaid",
                status="pending",
                total=0,
                discount=0,
                tax=0,
                service_charge=0,
                paid_amount=0,
                change_amount=0
            )

            subtotal = Decimal("0")
            valid_item_count = 0

            for item in items:

                try:

                    menu_item_id = int(
                        item.get("id")
                    )

                    quantity = int(
                        item.get("quantity")
                    )

                except (
                    TypeError,
                    ValueError,
                    AttributeError
                ):

                    raise ValueError(
                        "Invalid menu item data."
                    )

                if quantity <= 0:
                    continue

                try:

                    menu_item = (
                        MenuItem.objects
                        .select_related("category")
                        .get(
                            id=menu_item_id,
                            branch=branch,
                            available=True
                        )
                    )

                except MenuItem.DoesNotExist:

                    raise ValueError(
                        "One of the selected menu items is no longer available."
                    )

                price = menu_item.price

                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    price=price
                )

                subtotal += price * quantity
                valid_item_count += 1

                recipes = (
                    MenuItemIngredient.objects
                    .filter(
                        menu_item=menu_item,
                        ingredient__branch=branch,
                        ingredient__active=True
                    )
                    .select_related("ingredient")
                )

                for recipe in recipes:

                    usage_quantity = (
                        recipe.quantity * quantity
                    )

                    if (
                        recipe.ingredient.current_stock
                        < usage_quantity
                    ):

                        raise ValueError(
                            f"Insufficient stock for {recipe.ingredient.name}."
                        )

                    StockUsage.objects.create(
                        ingredient=recipe.ingredient,
                        quantity=usage_quantity,
                        reason=(
                            f"Order #{order.id} - "
                            f"{menu_item.name}"
                        )
                    )

            if valid_item_count == 0:

                raise ValueError(
                    "No valid items in order."
                )

            if discount > subtotal:
                discount = subtotal

            taxable_amount = subtotal - discount

            tax = (
                taxable_amount * TAX_RATE
            ).quantize(
                Decimal("0.01")
            )

            service_charge = FIXED_SERVICE_CHARGE

            grand_total = (
                taxable_amount
                + tax
                + service_charge
            ).quantize(
                Decimal("0.01")
            )

            if payment_method in [
                "card",
                "online"
            ]:

                paid_amount = grand_total
                change_amount = Decimal("0")
                payment_status = "paid"

            else:

                if paid_amount >= grand_total:

                    change_amount = (
                        paid_amount - grand_total
                    ).quantize(
                        Decimal("0.01")
                    )

                    payment_status = "paid"

                else:

                    change_amount = Decimal("0")
                    payment_status = "unpaid"

            order.total = grand_total
            order.discount = discount
            order.tax = tax
            order.service_charge = service_charge
            order.paid_amount = paid_amount
            order.change_amount = change_amount
            order.payment_status = payment_status

            order.save()

            if table:

                table.is_occupied = True

                table.save(
                    update_fields=["is_occupied"]
                )

        return JsonResponse(
            {
                "success": True,
                "order_id": order.id,
                "subtotal": str(subtotal),
                "discount": str(discount),
                "tax": str(tax),
                "service_charge": str(service_charge),
                "total": str(order.total),
                "paid_amount": str(order.paid_amount),
                "change_amount": str(order.change_amount),
                "payment_status": order.payment_status,
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid order data."
            },
            status=400
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )


# =========================================================
# UPDATE ORDER STATUS
# =========================================================

@login_required(login_url="login")
@order_staff_required
@require_POST
def update_order_status(request, order_id):

    try:

        data = json.loads(request.body)

        new_status = data.get("status")

        allowed_statuses = [
            "pending",
            "preparing",
            "ready",
            "served",
            "completed",
            "cancelled",
        ]

        if new_status not in allowed_statuses:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid order status."
                },
                status=400
            )

        branch = get_current_branch(request.user)

        if not branch:

            return JsonResponse(
                {
                    "success": False,
                    "message": "No branch assigned to this user."
                },
                status=400
            )

        try:

            with transaction.atomic():

                order = (
                    Order.objects
                    .select_for_update()
                    .select_related("table")
                    .get(
                        id=order_id,
                        branch=branch
                    )
                )

                order.status = new_status

                order.save(
                    update_fields=["status"]
                )

                if order.table:

                    order.table.is_occupied = (
                        new_status not in [
                            "completed",
                            "cancelled"
                        ]
                    )

                    order.table.save(
                        update_fields=["is_occupied"]
                    )

        except Order.DoesNotExist:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Order not found."
                },
                status=404
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Order status updated successfully.",
                "order_id": order.id,
                "status": order.status,
                "status_display": order.get_status_display(),
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid data."
            },
            status=400
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )


# =========================================================
# BILL
# =========================================================

@login_required(login_url="login")
def bill(request, order_id):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    order = get_object_or_404(
        Order,
        id=order_id,
        branch=branch
    )

    items = (
        order.items
        .select_related("menu_item")
        .all()
    )

    return render(
        request,
        "pos/bill.html",
        {
            "order": order,
            "items": items,
            "branch": branch,
        }
    )


# =========================================================
# KOT
# =========================================================

@login_required(login_url="login")
def kot(request, order_id):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    order = get_object_or_404(
        Order,
        id=order_id,
        branch=branch
    )

    items = (
        order.items
        .select_related("menu_item")
        .all()
    )

    return render(
        request,
        "pos/kot.html",
        {
            "order": order,
            "items": items,
            "branch": branch,
        }
    )


# =========================================================
# ORDER SUCCESS
# =========================================================

@login_required(login_url="login")
def order_success(request, order_id):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    order = get_object_or_404(
        Order,
        id=order_id,
        branch=branch
    )

    return render(
        request,
        "pos/success.html",
        {
            "order": order,
            "branch": branch,
        }
    )


# =========================================================
# SALES REPORT
# =========================================================

@login_required(login_url="login")
@manager_required
def sales_report(request):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    orders = (
        Order.objects
        .filter(branch=branch)
        .select_related("table")
        .order_by("-created_at")
    )

    start_date = request.GET.get(
        "start_date",
        ""
    )

    end_date = request.GET.get(
        "end_date",
        ""
    )

    if start_date:

        parsed_start = parse_date(start_date)

        if parsed_start:

            orders = orders.filter(
                created_at__date__gte=parsed_start
            )

    if end_date:

        parsed_end = parse_date(end_date)

        if parsed_end:

            orders = orders.filter(
                created_at__date__lte=parsed_end
            )

    completed_orders = orders.filter(
        status="completed"
    )

    total_sales = (
        completed_orders
        .aggregate(total=Sum("total"))
        .get("total")
        or Decimal("0")
    )

    return render(
        request,
        "pos/sales_report.html",
        {
            "orders": orders,
            "total_sales": total_sales,
            "total_orders": orders.count(),
            "completed_count": completed_orders.count(),
            "cancelled_count": orders.filter(
                status="cancelled"
            ).count(),
            "pending_count": orders.filter(
                status="pending"
            ).count(),
            "start_date": start_date,
            "end_date": end_date,
            "branch": branch,
        }
    )


# =========================================================
# INVENTORY
# =========================================================

@login_required(login_url="login")
@manager_required
def inventory(request):

    branch = get_current_branch(request.user)

    if not branch:
        raise PermissionDenied

    ingredients = (
        Ingredient.objects
        .filter(
            branch=branch,
            active=True
        )
        .order_by("name")
    )

    menu_items = (
        MenuItem.objects
        .filter(
            branch=branch,
            available=True
        )
        .prefetch_related("ingredients__ingredient")
        .order_by("name")
    )

    total_ingredients = ingredients.count()

    in_stock = 0
    low_stock = 0
    out_of_stock = 0

    low_stock_ingredients = []

    for ingredient in ingredients:

        if ingredient.is_out_of_stock:

            out_of_stock += 1
            low_stock_ingredients.append(ingredient)

        elif ingredient.is_low_stock:

            low_stock += 1
            low_stock_ingredients.append(ingredient)

        else:

            in_stock += 1

    recent_stock_in = (
        StockIn.objects
        .filter(
            ingredient__branch=branch
        )
        .select_related("ingredient")
        .order_by("-created_at")[:50]
    )

    recent_stock_usage = (
        StockUsage.objects
        .filter(
            ingredient__branch=branch
        )
        .select_related("ingredient")
        .order_by("-created_at")[:50]
    )

    recipes = (
        MenuItemIngredient.objects
        .filter(
            menu_item__branch=branch,
            ingredient__branch=branch
        )
        .select_related(
            "menu_item",
            "ingredient"
        )
        .order_by(
            "menu_item__name",
            "ingredient__name"
        )
    )

    return render(
        request,
        "pos/inventory.html",
        {
            "ingredients": ingredients,
            "menu_items": menu_items,
            "total_ingredients": total_ingredients,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "low_stock_ingredients": low_stock_ingredients,
            "recent_stock_in": recent_stock_in,
            "recent_stock_usage": recent_stock_usage,
            "recipes": recipes,
            "branch": branch,
        }
    )


# =========================================================
# ADD INGREDIENT
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_ingredient(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    unit = request.POST.get(
        "unit",
        "piece"
    ).strip()

    minimum_stock = request.POST.get(
        "minimum_stock",
        "0"
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient name is required."
            },
            status=400
        )

    if Ingredient.objects.filter(
        branch=branch,
        name__iexact=name,
        active=True
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This ingredient already exists in this branch."
            },
            status=400
        )

    allowed_units = [
        choice[0]
        for choice in Ingredient.UNIT_CHOICES
    ]

    if unit not in allowed_units:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid unit."
            },
            status=400
        )

    try:

        minimum_stock = decimal_value(
            minimum_stock
        )

        if minimum_stock < 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid minimum stock."
            },
            status=400
        )

    ingredient = Ingredient.objects.create(
        branch=branch,
        name=name,
        unit=unit,
        minimum_stock=minimum_stock,
        current_stock=0,
        active=True
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Ingredient added successfully.",
            "id": ingredient.id,
            "name": ingredient.name,
        }
    )


# =========================================================
# EDIT INGREDIENT
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_ingredient(request, ingredient_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        ingredient = Ingredient.objects.get(
            id=ingredient_id,
            branch=branch
        )

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient not found."
            },
            status=404
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    unit = request.POST.get(
        "unit",
        ""
    ).strip()

    minimum_stock = request.POST.get(
        "minimum_stock",
        "0"
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient name is required."
            },
            status=400
        )

    if Ingredient.objects.filter(
        branch=branch,
        name__iexact=name,
        active=True
    ).exclude(
        id=ingredient.id
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This ingredient already exists in this branch."
            },
            status=400
        )

    allowed_units = [
        choice[0]
        for choice in Ingredient.UNIT_CHOICES
    ]

    if unit not in allowed_units:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid unit."
            },
            status=400
        )

    try:

        minimum_stock = decimal_value(
            minimum_stock
        )

        if minimum_stock < 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid minimum stock."
            },
            status=400
        )

    ingredient.name = name
    ingredient.unit = unit
    ingredient.minimum_stock = minimum_stock

    ingredient.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Ingredient updated successfully."
        }
    )


# =========================================================
# DELETE INGREDIENT
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_ingredient(request, ingredient_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        ingredient = Ingredient.objects.get(
            id=ingredient_id,
            branch=branch
        )

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient not found."
            },
            status=404
        )

    if ingredient.menu_items.exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This ingredient is used in a recipe. "
                    "Remove it from recipes first."
                )
            },
            status=400
        )

    if ingredient.stock_entries.exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This ingredient has stock history. "
                    "It cannot be deleted."
                )
            },
            status=400
        )

    if ingredient.usage_entries.exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This ingredient has usage history. "
                    "It cannot be deleted."
                )
            },
            status=400
        )

    ingredient.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Ingredient deleted successfully."
        }
    )


# =========================================================
# ADD STOCK IN
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_stock_in(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    ingredient_id = request.POST.get(
        "ingredient_id",
        ""
    ).strip()

    quantity = request.POST.get(
        "quantity",
        ""
    ).strip()

    unit_price = request.POST.get(
        "unit_price",
        "0"
    ).strip()

    supplier = request.POST.get(
        "supplier",
        ""
    ).strip()

    note = request.POST.get(
        "note",
        ""
    ).strip()

    if not ingredient_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Please select an ingredient."
            },
            status=400
        )

    try:

        ingredient = Ingredient.objects.get(
            id=ingredient_id,
            branch=branch,
            active=True
        )

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient not found."
            },
            status=404
        )

    try:

        quantity = decimal_value(quantity)

        if quantity <= 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid quantity."
            },
            status=400
        )

    try:

        unit_price = decimal_value(
            unit_price
        )

        if unit_price < 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid unit price."
            },
            status=400
        )

    try:

        with transaction.atomic():

            stock = StockIn.objects.create(
                ingredient=ingredient,
                quantity=quantity,
                unit_price=unit_price,
                supplier=supplier,
                note=note
            )

            ingredient.refresh_from_db()

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Stock added successfully.",
            "stock_id": stock.id,
            "ingredient": ingredient.name,
            "quantity": str(quantity),
            "unit": ingredient.unit,
            "current_stock": str(
                ingredient.current_stock
            ),
        }
    )


# =========================================================
# ADD STOCK USAGE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_stock_usage(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    ingredient_id = request.POST.get(
        "ingredient_id",
        ""
    ).strip()

    quantity = request.POST.get(
        "quantity",
        ""
    ).strip()

    reason = request.POST.get(
        "reason",
        ""
    ).strip()

    note = request.POST.get(
        "note",
        ""
    ).strip()

    if not ingredient_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Please select an ingredient."
            },
            status=400
        )

    try:

        with transaction.atomic():

            ingredient = (
                Ingredient.objects
                .select_for_update()
                .get(
                    id=ingredient_id,
                    branch=branch,
                    active=True
                )
            )

            try:

                quantity = decimal_value(quantity)

                if quantity <= 0:
                    raise ValueError

            except (ValueError, TypeError, InvalidOperation):

                return JsonResponse(
                    {
                        "success": False,
                        "message": "Please enter a valid quantity."
                    },
                    status=400
                )

            if quantity > ingredient.current_stock:

                return JsonResponse(
                    {
                        "success": False,
                        "message": (
                            "Usage quantity cannot be greater "
                            "than current stock."
                        )
                    },
                    status=400
                )

            usage = StockUsage.objects.create(
                ingredient=ingredient,
                quantity=quantity,
                reason=reason,
                note=note
            )

            ingredient.refresh_from_db()

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Ingredient not found."
            },
            status=404
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Stock usage recorded successfully.",
            "usage_id": usage.id,
            "current_stock": str(
                ingredient.current_stock
            ),
        }
    )


# =========================================================
# ADD RECIPE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_recipe(request):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    menu_item_id = request.POST.get(
        "menu_item_id",
        ""
    ).strip()

    ingredient_id = request.POST.get(
        "ingredient_id",
        ""
    ).strip()

    quantity = request.POST.get(
        "quantity",
        ""
    ).strip()

    if not menu_item_id or not ingredient_id:

        return JsonResponse(
            {
                "success": False,
                "message": "Please select menu item and ingredient."
            },
            status=400
        )

    try:

        menu_item = MenuItem.objects.get(
            id=menu_item_id,
            branch=branch
        )

        ingredient = Ingredient.objects.get(
            id=ingredient_id,
            branch=branch,
            active=True
        )

    except (
        MenuItem.DoesNotExist,
        Ingredient.DoesNotExist
    ):

        return JsonResponse(
            {
                "success": False,
                "message": "Menu item or ingredient not found."
            },
            status=404
        )

    try:

        quantity = decimal_value(quantity)

        if quantity <= 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid quantity."
            },
            status=400
        )

    if MenuItemIngredient.objects.filter(
        menu_item=menu_item,
        ingredient=ingredient
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This ingredient is already in this recipe."
            },
            status=400
        )

    recipe = MenuItemIngredient.objects.create(
        menu_item=menu_item,
        ingredient=ingredient,
        quantity=quantity
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Recipe ingredient added successfully.",
            "recipe_id": recipe.id,
        }
    )


# =========================================================
# EDIT RECIPE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_recipe(request, recipe_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        recipe = (
            MenuItemIngredient.objects
            .select_related(
                "menu_item",
                "ingredient"
            )
            .get(
                id=recipe_id,
                menu_item__branch=branch,
                ingredient__branch=branch
            )
        )

    except MenuItemIngredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Recipe entry not found."
            },
            status=404
        )

    quantity = request.POST.get(
        "quantity",
        ""
    ).strip()

    try:

        quantity = decimal_value(quantity)

        if quantity <= 0:
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid quantity."
            },
            status=400
        )

    recipe.quantity = quantity
    recipe.save(update_fields=["quantity"])

    return JsonResponse(
        {
            "success": True,
            "message": "Recipe updated successfully."
        }
    )


# =========================================================
# DELETE RECIPE
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_recipe(request, recipe_id):

    branch = get_current_branch(request.user)

    if not branch:

        return JsonResponse(
            {
                "success": False,
                "message": "No branch assigned to this user."
            },
            status=400
        )

    try:

        recipe = MenuItemIngredient.objects.get(
            id=recipe_id,
            menu_item__branch=branch,
            ingredient__branch=branch
        )

    except MenuItemIngredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Recipe entry not found."
            },
            status=404
        )

    recipe.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Recipe ingredient removed successfully."
        }
    )


# =========================================================
# PUBLIC WEBSITE HOME
# =========================================================

def website_home(request):

    featured_items = (
        MenuItem.objects
        .filter(
            available=True,
            branch__active=True,
            branch__restaurant__active=True
        )
        .select_related(
            "category",
            "branch"
        )
        .order_by("id")[:6]
    )

    return render(
        request,
        "website/home.html",
        {
            "featured_items": featured_items,
        }
    )


# =========================================================
# PUBLIC WEBSITE MENU
# =========================================================

def website_menu(request):

    categories = (
        Category.objects
        .filter(
            branch__active=True,
            branch__restaurant__active=True,
            items__available=True
        )
        .prefetch_related("items")
        .distinct()
        .order_by("name")
    )

    return render(
        request,
        "website/menu.html",
        {
            "categories": categories,
        }
    )


# =========================================================
# PUBLIC WEBSITE ABOUT
# =========================================================

def website_about(request):

    return render(
        request,
        "website/about.html"
    )


# =========================================================
# PUBLIC WEBSITE GALLERY
# =========================================================

def website_gallery(request):

    return render(
        request,
        "website/gallery.html"
    )


# =========================================================
# PUBLIC WEBSITE CONTACT
# =========================================================

def website_contact(request):

    return render(
        request,
        "website/contact.html"
    )


# =========================================================
# PUBLIC WEBSITE ORDER PAGE
# =========================================================

def website_order(request):

    categories = (
        Category.objects
        .filter(
            branch__active=True,
            branch__restaurant__active=True,
            items__available=True
        )
        .prefetch_related("items")
        .distinct()
        .order_by("name")
    )

    return render(
        request,
        "website/order.html",
        {
            "categories": categories,
        }
    )


# =========================================================
# PUBLIC WEBSITE CREATE ORDER
# =========================================================

@require_POST
def website_create_order(request):

    try:

        data = json.loads(request.body)

        customer_name = (
            data.get(
                "customer_name",
                ""
            ).strip()
        )

        customer_phone = (
            data.get(
                "customer_phone",
                ""
            ).strip()
        )

        order_type = data.get(
            "order_type",
            "takeaway"
        )

        items = data.get(
            "items",
            []
        )

        if not customer_name:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter your name."
                },
                status=400
            )

        if not customer_phone:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter your phone number."
                },
                status=400
            )

        if order_type not in [
            "dine_in",
            "takeaway"
        ]:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid order type."
                },
                status=400
            )

        if not isinstance(items, list) or not items:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Your cart is empty."
                },
                status=400
            )

        branch = (
            Branch.objects
            .filter(
                active=True,
                restaurant__active=True
            )
            .order_by("id")
            .first()
        )

        if not branch:

            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Online ordering is currently unavailable."
                    )
                },
                status=400
            )

        with transaction.atomic():

            order = Order.objects.create(
                branch=branch,
                customer_name=customer_name,
                customer_phone=customer_phone,
                order_type=order_type,
                payment_method="cash",
                payment_status="unpaid",
                status="pending",
                total=0,
                discount=0,
                tax=0,
                service_charge=0,
                paid_amount=0,
                change_amount=0
            )

            subtotal = Decimal("0")
            valid_item_count = 0

            for item in items:

                try:

                    menu_item_id = int(
                        item.get("id")
                    )

                    quantity = int(
                        item.get("quantity")
                    )

                except (
                    TypeError,
                    ValueError,
                    AttributeError
                ):

                    raise ValueError(
                        "Invalid item data."
                    )

                if quantity <= 0:
                    continue

                try:

                    menu_item = (
                        MenuItem.objects
                        .get(
                            id=menu_item_id,
                            branch=branch,
                            available=True
                        )
                    )

                except MenuItem.DoesNotExist:

                    raise ValueError(
                        "One of the selected items is no longer available."
                    )

                price = menu_item.price

                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    price=price
                )

                subtotal += price * quantity
                valid_item_count += 1

                recipes = (
                    MenuItemIngredient.objects
                    .filter(
                        menu_item=menu_item,
                        ingredient__branch=branch,
                        ingredient__active=True
                    )
                    .select_related("ingredient")
                )

                for recipe in recipes:

                    usage_quantity = (
                        recipe.quantity * quantity
                    )

                    if (
                        recipe.ingredient.current_stock
                        < usage_quantity
                    ):

                        raise ValueError(
                            f"Insufficient stock for {recipe.ingredient.name}."
                        )

                    StockUsage.objects.create(
                        ingredient=recipe.ingredient,
                        quantity=usage_quantity,
                        reason=(
                            f"Website Order #{order.id} - "
                            f"{menu_item.name}"
                        )
                    )

            if valid_item_count == 0:

                raise ValueError(
                    "No valid items were found."
                )

            tax = (
                subtotal * TAX_RATE
            ).quantize(
                Decimal("0.01")
            )

            service_charge = FIXED_SERVICE_CHARGE

            grand_total = (
                subtotal
                + tax
                + service_charge
            ).quantize(
                Decimal("0.01")
            )

            order.total = grand_total
            order.tax = tax
            order.service_charge = service_charge

            order.save(
                update_fields=[
                    "total",
                    "tax",
                    "service_charge"
                ]
            )

        return JsonResponse(
            {
                "success": True,
                "order_id": order.id,
                "subtotal": str(subtotal),
                "tax": str(tax),
                "service_charge": str(service_charge),
                "total": str(grand_total),
                "message": "Your order has been placed successfully.",
            }
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid order data."
            },
            status=400
        )

    except Exception as e:

        return JsonResponse(
            {
                "success": False,
                "message": str(e)
            },
            status=400
        )


# =========================================================
# PUBLIC WEBSITE ORDER SUCCESS
# =========================================================

def website_order_success(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id
    )

    return render(
        request,
        "website/order_success.html",
        {
            "order": order,
        }
    )


# =========================================================
# BRANCH MANAGEMENT
# =========================================================

@login_required(login_url="login")
@manager_required
def branches(request):

    branches = (
        Branch.objects
        .select_related("restaurant")
        .order_by(
            "restaurant__name",
            "name"
        )
    )

    return render(
        request,
        "pos/branches.html",
        {
            "branches": branches,
        }
    )


# =========================================================
# ADD BRANCH
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def add_branch(request):

    name = request.POST.get(
        "name",
        ""
    ).strip()

    address = request.POST.get(
        "address",
        ""
    ).strip()

    phone = request.POST.get(
        "phone",
        ""
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Branch name is required."
            },
            status=400
        )

    restaurant = (
        Restaurant.objects
        .filter(active=True)
        .order_by("id")
        .first()
    )

    if not restaurant:

        return JsonResponse(
            {
                "success": False,
                "message": "Please create a restaurant first."
            },
            status=400
        )

    if Branch.objects.filter(
        restaurant=restaurant,
        name__iexact=name
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This branch already exists."
            },
            status=400
        )

    branch = Branch.objects.create(
        restaurant=restaurant,
        name=name,
        address=address,
        phone=phone,
        active=True
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Branch added successfully.",
            "id": branch.id,
            "name": branch.name,
        }
    )


# =========================================================
# EDIT BRANCH
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def edit_branch(request, branch_id):

    try:

        branch = Branch.objects.get(
            id=branch_id
        )

    except Branch.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Branch not found."
            },
            status=404
        )

    name = request.POST.get(
        "name",
        ""
    ).strip()

    address = request.POST.get(
        "address",
        ""
    ).strip()

    phone = request.POST.get(
        "phone",
        ""
    ).strip()

    if not name:

        return JsonResponse(
            {
                "success": False,
                "message": "Branch name is required."
            },
            status=400
        )

    if Branch.objects.filter(
        restaurant=branch.restaurant,
        name__iexact=name
    ).exclude(
        id=branch.id
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This branch already exists."
            },
            status=400
        )

    branch.name = name
    branch.address = address
    branch.phone = phone

    branch.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Branch updated successfully."
        }
    )


# =========================================================
# DELETE BRANCH
# =========================================================

@login_required(login_url="login")
@manager_required
@require_POST
def delete_branch(request, branch_id):

    try:

        branch = Branch.objects.get(
            id=branch_id
        )

    except Branch.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message": "Branch not found."
            },
            status=404
        )

    if UserBranch.objects.filter(
        branch=branch
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This branch is assigned to users "
                    "and cannot be deleted."
                )
            },
            status=400
        )

    if (
        branch.categories.exists()
        or branch.menu_items.exists()
        or branch.tables.exists()
        or branch.orders.exists()
        or branch.ingredients.exists()
    ):

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This branch contains existing data "
                    "and cannot be deleted."
                )
            },
            status=400
        )

    branch.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Branch deleted successfully."
        }
    )