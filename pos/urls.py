from django.urls import path

from . import views


urlpatterns = [

    # =====================================================
    # LOGIN / LOGOUT
    # =====================================================

    path(
       "login/",
       views.login_view,
        name="login"
    ),

    path(
       "logout/",
        views.logout_view,
        name="logout"
    ),
    
    # =====================================================
    # POS
    # =====================================================

    path(
        "",
        views.pos_home,
        name="pos_home"
    ),

    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),

    # =====================================================
    # MENU
    # =====================================================

    path(
        "menu/",
        views.menu,
        name="menu"
    ),

    # =====================================================
    # CATEGORY
    # =====================================================

    path(
        "add-category/",
        views.add_category,
        name="add_category"
    ),

    path(
        "edit-category/<int:category_id>/",
        views.edit_category,
        name="edit_category"
    ),

    path(
        "delete-category/<int:category_id>/",
        views.delete_category,
        name="delete_category"
    ),

    # =====================================================
    # MENU ITEMS
    # =====================================================

    path(
        "add-menu-item/",
        views.add_menu_item,
        name="add_menu_item"
    ),

    path(
        "edit-menu-item/<int:item_id>/",
        views.edit_menu_item,
        name="edit_menu_item"
    ),

    path(
        "delete-menu-item/<int:item_id>/",
        views.delete_menu_item,
        name="delete_menu_item"
    ),

    # =====================================================
    # TABLE MANAGEMENT
    # =====================================================

    path(
        "add-table/",
        views.add_table,
        name="add_table"
    ),

    path(
        "edit-table/<int:table_id>/",
        views.edit_table,
        name="edit_table"
    ),

    path(
        "delete-table/<int:table_id>/",
        views.delete_table,
        name="delete_table"
    ),

    # =====================================================
    # ORDERS
    # =====================================================

    path(
        "create-order/",
        views.create_order,
        name="create_order"
    ),

    path(
        "update-order-status/<int:order_id>/",
        views.update_order_status,
        name="update_order_status"
    ),

    # =====================================================
    # KOT
    # =====================================================

    path(
        "kot/<int:order_id>/",
        views.kot,
        name="kot"
    ),

    # =====================================================
    # BILL
    # =====================================================

    path(
        "bill/<int:order_id>/",
        views.bill,
        name="bill"
    ),

    # =====================================================
    # ORDER SUCCESS
    # =====================================================

    path(
        "order-success/<int:order_id>/",
        views.order_success,
        name="order_success"
    ),

    # =====================================================
    # SALES REPORT
    # =====================================================

    path(
        "sales-report/",
        views.sales_report,
        name="sales_report"
    ),

    # =====================================================
    # INVENTORY
    # =====================================================

    path(
        "inventory/",
        views.inventory,
        name="inventory"
    ),

    # =====================================================
    # INGREDIENT MANAGEMENT
    # =====================================================

    path(
        "add-ingredient/",
        views.add_ingredient,
        name="add_ingredient"
    ),

    path(
        "edit-ingredient/<int:ingredient_id>/",
        views.edit_ingredient,
        name="edit_ingredient"
    ),

    path(
        "delete-ingredient/<int:ingredient_id>/",
        views.delete_ingredient,
        name="delete_ingredient"
    ),

    # =====================================================
    # STOCK IN
    # =====================================================

    path(
        "add-stock-in/",
        views.add_stock_in,
        name="add_stock_in"
    ),

    # =====================================================
    # STOCK USAGE
    # =====================================================

    path(
        "add-stock-usage/",
        views.add_stock_usage,
        name="add_stock_usage"
    ),

    # =====================================================
    # RECIPE / MENU INGREDIENTS
    # =====================================================

    path(
        "add-recipe/",
        views.add_recipe,
        name="add_recipe"
    ),

    path(
        "edit-recipe/<int:recipe_id>/",
        views.edit_recipe,
        name="edit_recipe"
    ),

    path(
        "delete-recipe/<int:recipe_id>/",
        views.delete_recipe,
        name="delete_recipe"
    ),
]