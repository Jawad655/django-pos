from django.shortcuts import render, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from decimal import Decimal
import json

from .models import (
    Category,
    MenuItem,
    Table,
    Order,
    OrderItem,
    Ingredient,
    StockIn,
    StockUsage,
    MenuItemIngredient,
)


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

                    next_url = request.GET.get(
                        "next"
                    )

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
# POS HOME
# =========================================================

@login_required(login_url="login")
def pos_home(request):

    categories = Category.objects.all()

    menu_items = MenuItem.objects.filter(
        available=True
    ).select_related(
        "category"
    )

    tables = Table.objects.all().order_by(
        "number"
    )

    orders = Order.objects.prefetch_related(
        "items"
    ).select_related(
        "table"
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "pos/pos.html",
        {
            "categories": categories,
            "menu_items": menu_items,
            "tables": tables,
            "orders": orders,
        }
    )


# =========================================================
# TABLE MANAGEMENT
# =========================================================

@login_required(login_url="login")
@require_POST
def add_table(request):

    try:

        data = json.loads(
            request.body
        )

        number = data.get(
            "number"
        )

        capacity = data.get(
            "capacity",
            4
        )

        if not number:

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

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid table number."
                },
                status=400
            )

        if Table.objects.filter(
            number=number
        ).exists():

            return JsonResponse(
                {
                    "success": False,
                    "message": "This table number already exists."
                },
                status=400
            )

        try:

            capacity = int(capacity)

            if capacity <= 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            capacity = 4

        table = Table.objects.create(
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
                    "is_occupied": table.is_occupied
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
@require_POST
def edit_table(request, table_id):

    try:

        table = Table.objects.get(
            id=table_id
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

        data = json.loads(
            request.body
        )

        number = data.get(
            "number"
        )

        capacity = data.get(
            "capacity",
            table.capacity
        )

        if not number:

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

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid table number."
                },
                status=400
            )

        if Table.objects.filter(
            number=number
        ).exclude(
            id=table.id
        ).exists():

            return JsonResponse(
                {
                    "success": False,
                    "message": "This table number already exists."
                },
                status=400
            )

        try:

            capacity = int(capacity)

            if capacity <= 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

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
                    "is_occupied": table.is_occupied
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
@require_POST
def delete_table(request, table_id):

    try:

        table = Table.objects.get(
            id=table_id
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
        table=table
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This table has order history "
                    "and cannot be deleted."
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

    orders = Order.objects.all()

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

    total_sales = orders.filter(
        status="completed"
    ).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0")

    today = timezone.localdate()

    today_orders = orders.filter(
        created_at__date=today
    )

    today_sales = today_orders.filter(
        status="completed"
    ).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0")

    total_menu_items = MenuItem.objects.count()

    total_categories = Category.objects.count()

    total_tables = Table.objects.count()

    occupied_tables = Table.objects.filter(
        is_occupied=True
    ).count()

    low_stock_items = [
        ingredient
        for ingredient in Ingredient.objects.filter(
            active=True
        )
        if ingredient.is_low_stock
    ]

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
        }
    )


# =========================================================
# MENU
# =========================================================

@login_required(login_url="login")
def menu(request):

    categories = Category.objects.prefetch_related(
        "items"
    ).all()

    ingredients = Ingredient.objects.filter(
        active=True
    ).order_by(
        "name"
    )

    menu_items = MenuItem.objects.select_related(
        "category"
    ).prefetch_related(
        "ingredients__ingredient"
    ).all()

    return render(
        request,
        "pos/menu.html",
        {
            "categories": categories,
            "ingredients": ingredients,
            "menu_items": menu_items,
        }
    )


# =========================================================
# ADD CATEGORY
# =========================================================

@login_required(login_url="login")
@require_POST
def add_category(request):

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
        name__iexact=name
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This category already exists."
            },
            status=400
        )

    category = Category.objects.create(
        name=name
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Category added successfully.",
            "id": category.id,
            "name": category.name
        }
    )


# =========================================================
# EDIT CATEGORY
# =========================================================

@login_required(login_url="login")
@require_POST
def edit_category(request, category_id):

    try:

        category = Category.objects.get(
            id=category_id
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
        name__iexact=name
    ).exclude(
        id=category.id
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": "This category already exists."
            },
            status=400
        )

    category.name = name

    category.save()

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
@require_POST
def delete_category(request, category_id):

    try:

        category = Category.objects.get(
            id=category_id
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
                "message":
                    "This category contains menu items. "
                    "Delete or move the items first."
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
@require_POST
def add_menu_item(request):

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

    available = (
        request.POST.get("available")
        == "on"
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
            id=category_id
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

        price = Decimal(price)

        if price <= 0:
            raise ValueError

    except (
        ValueError,
        TypeError
    ):

        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid price."
            },
            status=400
        )

    image = request.FILES.get(
        "image"
    )

    MenuItem.objects.create(
        category=category,
        name=name,
        price=price,
        image=image,
        available=available,
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
@require_POST
def edit_menu_item(request, item_id):

    try:

        item = MenuItem.objects.get(
            id=item_id
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

    available = (
        request.POST.get("available")
        == "on"
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
            id=category_id
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

        price = Decimal(price)

        if price <= 0:
            raise ValueError

    except (
        ValueError,
        TypeError
    ):

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
    item.available = available

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
@require_POST
def delete_menu_item(request, item_id):

    try:

        item = MenuItem.objects.get(
            id=item_id
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
                "message":
                    "This item has already been used "
                    "in an order. Make it unavailable "
                    "instead of deleting it."
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
# CREATE ORDER
# =========================================================

@login_required(login_url="login")
@require_POST
def create_order(request):

    try:

        data = json.loads(
            request.body
        )

        table_id = data.get(
            "table_id"
        )

        items = data.get(
            "items",
            []
        )

        order_type = data.get(
            "order_type",
            "dine_in"
        )

        payment_method = data.get(
            "payment_method",
            "cash"
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

        if not items:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Cart is empty."
                },
                status=400
            )

        table = None

        if table_id:

            try:

                table = Table.objects.get(
                    id=table_id
                )

            except Table.DoesNotExist:

                return JsonResponse(
                    {
                        "success": False,
                        "message": "Table not found."
                    },
                    status=404
                )

        order = Order.objects.create(
            table=table,
            order_type=order_type,
            payment_method=payment_method,
            payment_status="paid",
            status="pending",
            total=0
        )

        total = Decimal("0")

        for item in items:

            try:

                menu_item = MenuItem.objects.get(
                    id=item["id"],
                    available=True
                )

                quantity = int(
                    item["quantity"]
                )

            except (
                MenuItem.DoesNotExist,
                KeyError,
                ValueError,
                TypeError
            ):

                order.delete()

                return JsonResponse(
                    {
                        "success": False,
                        "message":
                            "Invalid menu item or quantity."
                    },
                    status=400
                )

            if quantity <= 0:
                continue

            price = menu_item.price

            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=quantity,
                price=price
            )

            total += price * quantity

            for recipe in menu_item.ingredients.select_related(
                "ingredient"
            ):

                usage_quantity = (
                    recipe.quantity *
                    quantity
                )

                StockUsage.objects.create(
                    ingredient=recipe.ingredient,
                    quantity=usage_quantity,
                    reason=(
                        f"Order #{order.id} - "
                        f"{menu_item.name}"
                    )
                )

        if not order.items.exists():

            order.delete()

            return JsonResponse(
                {
                    "success": False,
                    "message": "No valid items in order."
                },
                status=400
            )

        order.total = total

        order.save()

        if table:

            table.is_occupied = True

            table.save(
                update_fields=[
                    "is_occupied"
                ]
            )

        return JsonResponse(
            {
                "success": True,
                "order_id": order.id,
                "total": str(
                    order.total
                )
            }
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
@require_POST
def update_order_status(
    request,
    order_id
):

    try:

        data = json.loads(
            request.body
        )

        new_status = data.get(
            "status"
        )

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

        try:

            order = Order.objects.select_related(
                "table"
            ).get(
                id=order_id
            )

        except Order.DoesNotExist:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Order not found."
                },
                status=404
            )

        order.status = new_status

        order.save()

        if order.table:

            order.table.is_occupied = (
                new_status not in [
                    "completed",
                    "cancelled"
                ]
            )

            order.table.save(
                update_fields=[
                    "is_occupied"
                ]
            )

        return JsonResponse(
            {
                "success": True,
                "message":
                    "Order status updated successfully.",
                "order_id": order.id,
                "status": order.status,
                "status_display":
                    order.get_status_display()
            }
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

    try:

        order = Order.objects.get(
            id=order_id
        )

    except Order.DoesNotExist:

        return render(
            request,
            "pos/error.html",
            {
                "message": "Order not found."
            }
        )

    items = order.items.select_related(
        "menu_item"
    )

    return render(
        request,
        "pos/bill.html",
        {
            "order": order,
            "items": items,
        }
    )


# =========================================================
# KOT
# =========================================================

@login_required(login_url="login")
def kot(request, order_id):

    try:

        order = Order.objects.get(
            id=order_id
        )

    except Order.DoesNotExist:

        return render(
            request,
            "pos/error.html",
            {
                "message": "Order not found."
            }
        )

    items = order.items.select_related(
        "menu_item"
    )

    return render(
        request,
        "pos/kot.html",
        {
            "order": order,
            "items": items,
        }
    )


# =========================================================
# ORDER SUCCESS
# =========================================================

@login_required(login_url="login")
def order_success(
    request,
    order_id
):

    try:

        order = Order.objects.get(
            id=order_id
        )

    except Order.DoesNotExist:

        return render(
            request,
            "pos/error.html",
            {
                "message": "Order not found."
            }
        )

    return render(
        request,
        "pos/success.html",
        {
            "order": order
        }
    )


# =========================================================
# SALES REPORT
# =========================================================

@login_required(login_url="login")
def sales_report(request):

    orders = Order.objects.all().order_by(
        "-created_at"
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

        parsed_start = parse_date(
            start_date
        )

        if parsed_start:

            orders = orders.filter(
                created_at__date__gte=parsed_start
            )

    if end_date:

        parsed_end = parse_date(
            end_date
        )

        if parsed_end:

            orders = orders.filter(
                created_at__date__lte=parsed_end
            )

    completed_orders = orders.filter(
        status="completed"
    )

    total_sales = completed_orders.aggregate(
        total=Sum("total")
    )["total"] or Decimal("0")

    return render(
        request,
        "pos/sales_report.html",
        {
            "orders": orders,
            "total_sales": total_sales,
            "total_orders": orders.count(),
            "completed_count":
                completed_orders.count(),
            "cancelled_count":
                orders.filter(
                    status="cancelled"
                ).count(),
            "pending_count":
                orders.filter(
                    status="pending"
                ).count(),
            "start_date": start_date,
            "end_date": end_date,
        }
    )


# =========================================================
# INVENTORY
# =========================================================

@login_required(login_url="login")
def inventory(request):

    ingredients = Ingredient.objects.filter(
        active=True
    ).order_by(
        "name"
    )

    menu_items = MenuItem.objects.filter(
        available=True
    ).prefetch_related(
        "ingredients__ingredient"
    ).order_by(
        "name"
    )

    total_ingredients = ingredients.count()

    in_stock = 0
    low_stock = 0
    out_of_stock = 0

    low_stock_ingredients = []

    for ingredient in ingredients:

        if ingredient.is_out_of_stock:

            out_of_stock += 1

            low_stock_ingredients.append(
                ingredient
            )

        elif ingredient.is_low_stock:

            low_stock += 1

            low_stock_ingredients.append(
                ingredient
            )

        else:

            in_stock += 1

    recent_stock_in = StockIn.objects.select_related(
        "ingredient"
    ).order_by(
        "-created_at"
    )[:50]

    recent_stock_usage = StockUsage.objects.select_related(
        "ingredient"
    ).order_by(
        "-created_at"
    )[:50]

    recipes = MenuItemIngredient.objects.select_related(
        "menu_item",
        "ingredient"
    ).order_by(
        "menu_item__name",
        "ingredient__name"
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
            "low_stock_ingredients":
                low_stock_ingredients,
            "recent_stock_in":
                recent_stock_in,
            "recent_stock_usage":
                recent_stock_usage,
            "recipes": recipes,
        }
    )


# =========================================================
# ADD INGREDIENT
# =========================================================

@login_required(login_url="login")
@require_POST
def add_ingredient(request):

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
                "message":
                    "Ingredient name is required."
            },
            status=400
        )

    if Ingredient.objects.filter(
        name__iexact=name,
        active=True
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This ingredient already exists."
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

        minimum_stock = Decimal(
            minimum_stock or "0"
        )

        if minimum_stock < 0:
            raise ValueError

    except (
        ValueError,
        TypeError
    ):

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Invalid minimum stock."
            },
            status=400
        )

    ingredient = Ingredient.objects.create(
        name=name,
        unit=unit,
        minimum_stock=minimum_stock,
        current_stock=0,
        active=True
    )

    return JsonResponse(
        {
            "success": True,
            "message":
                "Ingredient added successfully.",
            "id": ingredient.id,
            "name": ingredient.name
        }
    )


# =========================================================
# EDIT INGREDIENT
# =========================================================

@login_required(login_url="login")
@require_POST
def edit_ingredient(
    request,
    ingredient_id
):

    try:

        ingredient = Ingredient.objects.get(
            id=ingredient_id
        )

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Ingredient not found."
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
                "message":
                    "Ingredient name is required."
            },
            status=400
        )

    if Ingredient.objects.filter(
        name__iexact=name,
        active=True
    ).exclude(
        id=ingredient.id
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This ingredient already exists."
            },
            status=400
        )

    try:

        minimum_stock = Decimal(
            minimum_stock or "0"
        )

        if minimum_stock < 0:
            raise ValueError

    except (
        ValueError,
        TypeError
    ):

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Invalid minimum stock."
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

    ingredient.name = name
    ingredient.unit = unit
    ingredient.minimum_stock = minimum_stock

    ingredient.save()

    return JsonResponse(
        {
            "success": True,
            "message":
                "Ingredient updated successfully."
        }
    )


# =========================================================
# DELETE INGREDIENT
# =========================================================

@login_required(login_url="login")
@require_POST
def delete_ingredient(
    request,
    ingredient_id
):

    try:

        ingredient = Ingredient.objects.get(
            id=ingredient_id
        )

    except Ingredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Ingredient not found."
            },
            status=404
        )

    if ingredient.menu_items.exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This ingredient is used in a recipe. "
                    "Remove it from recipes first."
            },
            status=400
        )

    if ingredient.stock_entries.exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This ingredient has stock history. "
                    "It cannot be deleted."
            },
            status=400
        )

    if ingredient.usage_entries.exists():

        return JsonResponse(
            {
                "success": False,
                "message":
                    "This ingredient has usage history. "
                    "It cannot be deleted."
            },
            status=400
        )

    ingredient.delete()

    return JsonResponse(
        {
            "success": True,
            "message":
                "Ingredient deleted successfully."
        }
    )


# =========================================================
# ADD STOCK IN
# =========================================================

@login_required(login_url="login")
@require_POST
def add_stock_in(request):

    try:

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
                    "message":
                        "Please select an ingredient."
                },
                status=400
            )

        try:

            ingredient = Ingredient.objects.get(
                id=ingredient_id,
                active=True
            )

        except Ingredient.DoesNotExist:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Ingredient not found."
                },
                status=404
            )

        try:

            quantity = Decimal(
                quantity
            )

            if quantity <= 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Please enter a valid quantity."
                },
                status=400
            )

        try:

            unit_price = Decimal(
                unit_price or "0"
            )

            if unit_price < 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Please enter a valid unit price."
                },
                status=400
            )

        stock = StockIn.objects.create(
            ingredient=ingredient,
            quantity=quantity,
            unit_price=unit_price,
            supplier=supplier,
            note=note
        )

        return JsonResponse(
            {
                "success": True,
                "message":
                    "Stock added successfully.",
                "stock_id": stock.id,
                "ingredient": ingredient.name,
                "quantity": str(quantity),
                "unit": ingredient.unit,
                "current_stock":
                    str(
                        ingredient.current_stock
                    )
            }
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
# ADD STOCK USAGE
# =========================================================

@login_required(login_url="login")
@require_POST
def add_stock_usage(request):

    try:

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
                    "message":
                        "Please select an ingredient."
                },
                status=400
            )

        try:

            ingredient = Ingredient.objects.get(
                id=ingredient_id,
                active=True
            )

        except Ingredient.DoesNotExist:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Ingredient not found."
                },
                status=404
            )

        try:

            quantity = Decimal(
                quantity
            )

            if quantity <= 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Please enter a valid quantity."
                },
                status=400
            )

        if quantity > ingredient.current_stock:

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Usage quantity cannot be greater "
                        "than current stock."
                },
                status=400
            )

        usage = StockUsage.objects.create(
            ingredient=ingredient,
            quantity=quantity,
            reason=reason,
            note=note
        )

        return JsonResponse(
            {
                "success": True,
                "message":
                    "Stock usage recorded successfully.",
                "usage_id": usage.id,
                "current_stock":
                    str(
                        ingredient.current_stock
                    )
            }
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
# ADD RECIPE
# =========================================================

@login_required(login_url="login")
@require_POST
def add_recipe(request):

    try:

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
                    "message":
                        "Please select menu item and ingredient."
                },
                status=400
            )

        try:

            menu_item = MenuItem.objects.get(
                id=menu_item_id
            )

            ingredient = Ingredient.objects.get(
                id=ingredient_id,
                active=True
            )

        except (
            MenuItem.DoesNotExist,
            Ingredient.DoesNotExist
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Menu item or ingredient not found."
                },
                status=404
            )

        try:

            quantity = Decimal(
                quantity
            )

            if quantity <= 0:
                raise ValueError

        except (
            ValueError,
            TypeError
        ):

            return JsonResponse(
                {
                    "success": False,
                    "message":
                        "Please enter a valid quantity."
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
                    "message":
                        "This ingredient is already "
                        "in this recipe."
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
                "message":
                    "Recipe ingredient added successfully.",
                "recipe_id": recipe.id
            }
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
# EDIT RECIPE
# =========================================================

@login_required(login_url="login")
@require_POST
def edit_recipe(
    request,
    recipe_id
):

    try:

        recipe = MenuItemIngredient.objects.get(
            id=recipe_id
        )

    except MenuItemIngredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Recipe entry not found."
            },
            status=404
        )

    quantity = request.POST.get(
        "quantity",
        ""
    ).strip()

    try:

        quantity = Decimal(
            quantity
        )

        if quantity <= 0:
            raise ValueError

    except (
        ValueError,
        TypeError
    ):

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Please enter a valid quantity."
            },
            status=400
        )

    recipe.quantity = quantity

    recipe.save()

    return JsonResponse(
        {
            "success": True,
            "message":
                "Recipe updated successfully."
        }
    )


# =========================================================
# DELETE RECIPE
# =========================================================

@login_required(login_url="login")
@require_POST
def delete_recipe(
    request,
    recipe_id
):

    try:

        recipe = MenuItemIngredient.objects.get(
            id=recipe_id
        )

    except MenuItemIngredient.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "message":
                    "Recipe entry not found."
            },
            status=404
        )

    recipe.delete()

    return JsonResponse(
        {
            "success": True,
            "message":
                "Recipe ingredient removed successfully."
        }
    )