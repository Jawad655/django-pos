from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db import models

from .models import (
    Restaurant,
    Branch,
    UserBranch,
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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
    )


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "category",
        "price",
        "available",
    )

    list_filter = (
        "category",
        "available",
    )

    search_fields = (
        "name",
    )


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):

    list_display = (
        "number",
        "capacity",
        "is_occupied",
    )

    list_filter = (
        "is_occupied",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "table",
        "order_type",
        "payment_method",
        "payment_status",
        "status",
        "total",
        "created_at",
    )

    list_filter = (
        "status",
        "order_type",
        "created_at",
        "payment_method",
        "payment_status",
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "order",
        "menu_item",
        "quantity",
        "price",
    )


# =====================================================
# INVENTORY
# =====================================================

class StockStatusFilter(SimpleListFilter):

    title = "Stock Status"

    parameter_name = "stock_status"

    def lookups(self, request, model_admin):

        return (
            ("in_stock", "🟢 In Stock"),
            ("low_stock", "🟠 Low Stock"),
            ("out_of_stock", "🔴 Out of Stock"),
        )

    def queryset(self, request, queryset):

        if self.value() == "in_stock":

            return queryset.filter(
                current_stock__gt=models.F("minimum_stock")
            )

        if self.value() == "low_stock":

            return queryset.filter(
                current_stock__gt=0,
                current_stock__lte=models.F("minimum_stock")
            )

        if self.value() == "out_of_stock":

            return queryset.filter(
                current_stock__lte=0
            )

        return queryset


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "unit",
        "current_stock",
        "minimum_stock",
        "stock_status",
        "active",
    )

    list_filter = (
        StockStatusFilter,
        "unit",
        "active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "name",
    )

    @admin.display(
        description="Stock Status"
    )
    def stock_status(self, obj):

        if obj.is_out_of_stock:

            return "🔴 Out of Stock"

        if obj.is_low_stock:

            return "🟠 Low Stock"

        return "🟢 In Stock"


# =====================================================
# STOCK IN
# =====================================================

@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "ingredient",
        "quantity",
        "unit_price",
        "total_cost_display",
        "supplier",
        "created_at",
    )

    list_filter = (
        "ingredient",
        "created_at",
    )

    search_fields = (
        "ingredient__name",
        "supplier",
    )

    ordering = (
        "-created_at",
    )

    @admin.display(
        description="Total Cost"
    )
    def total_cost_display(self, obj):

        return obj.total_cost

 # =====================================================
# STOCK USAGE
# =====================================================

@admin.register(StockUsage)
class StockUsageAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "ingredient",
        "quantity",
        "reason",
        "created_at",
    )

    list_filter = (
        "ingredient",
        "created_at",
    )

    search_fields = (
        "ingredient__name",
        "reason",
    )

    ordering = (
        "-created_at",
    )   

   # =====================================================
# MENU ITEM INGREDIENTS / RECIPES
# =====================================================

@admin.register(MenuItemIngredient)
class MenuItemIngredientAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "menu_item",
        "ingredient",
        "quantity",
    )

    list_filter = (
        "menu_item",
        "ingredient",
    )

    search_fields = (
        "menu_item__name",
        "ingredient__name",
    )

    ordering = (
        "menu_item",
        "ingredient",
    )


# =====================================================
# RESTAURANT
# =====================================================

@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "phone",
        "active",
        "created_at",
    )

    list_filter = (
        "active",
    )

    search_fields = (
        "name",
        "phone",
        "address",
    )

    ordering = (
        "name",
    )


# =====================================================
# BRANCH
# =====================================================

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "restaurant",
        "name",
        "phone",
        "active",
        "created_at",
    )

    list_filter = (
        "restaurant",
        "active",
    )

    search_fields = (
        "name",
        "address",
        "phone",
        "restaurant__name",
    )

    ordering = (
        "restaurant",
        "name",
    )


# =====================================================
# USER BRANCH
# =====================================================

@admin.register(UserBranch)
class UserBranchAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "branch",
    )

    list_filter = (
        "branch",
    )

    search_fields = (
        "user__username",
        "branch__name",
        "branch__restaurant__name",
    )

    ordering = (
        "user__username",
    )