from django.db import models
from django.db.models import Q


# =========================================================
# RESTAURANT
# =========================================================

class Restaurant(models.Model):

    name = models.CharField(
        max_length=150
    )

    address = models.TextField(
        blank=True,
        default=""
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return self.name


# =========================================================
# BRANCH
# =========================================================

class Branch(models.Model):

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="branches"
    )

    name = models.CharField(
        max_length=150
    )

    address = models.TextField(
        blank=True,
        default=""
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "restaurant",
                    "name"
                ],
                name="unique_branch_name_per_restaurant"
            )
        ]

        ordering = [
            "name"
        ]

    def __str__(self):

        return (
            f"{self.restaurant.name} - "
            f"{self.name}"
        )


# =========================================================
# USER BRANCH
# =========================================================

class UserBranch(models.Model):

    user = models.OneToOneField(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="branch_access"
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="users"
    )

    def __str__(self):

        return (
            f"{self.user.username} - "
            f"{self.branch.name}"
        )


# =========================================================
# CATEGORY
# =========================================================

class Category(models.Model):

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(
        max_length=100
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "branch",
                    "name"
                ],
                name="unique_category_name_per_branch"
            )
        ]

        ordering = [
            "name"
        ]

    def __str__(self):

        return self.name


# =========================================================
# MENU ITEM
# =========================================================

class MenuItem(models.Model):

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="menu_items"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="items"
    )

    name = models.CharField(
        max_length=150
    )

    description = models.TextField(
        blank=True,
        default=""
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    image = models.ImageField(
        upload_to="menu_items/",
        blank=True,
        null=True
    )

    available = models.BooleanField(
        default=True
    )

    class Meta:

        ordering = [
            "name"
        ]

    def __str__(self):

        return self.name


# =========================================================
# TABLE
# =========================================================

class Table(models.Model):

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="tables"
    )

    number = models.PositiveIntegerField()

    capacity = models.PositiveIntegerField(
        default=4
    )

    is_occupied = models.BooleanField(
        default=False
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "branch",
                    "number"
                ],
                name="unique_table_number_per_branch"
            )
        ]

        ordering = [
            "number"
        ]

    def __str__(self):

        return (
            f"{self.branch.name} - "
            f"Table {self.number}"
        )


# =========================================================
# ORDER
# =========================================================

class Order(models.Model):

    ORDER_TYPES = [
        (
            "dine_in",
            "Dine In"
        ),
        (
            "takeaway",
            "Takeaway"
        ),
    ]

    STATUS_CHOICES = [
        (
            "pending",
            "Pending"
        ),
        (
            "preparing",
            "Preparing"
        ),
        (
            "ready",
            "Ready"
        ),
        (
            "served",
            "Served"
        ),
        (
            "completed",
            "Completed"
        ),
        (
            "cancelled",
            "Cancelled"
        ),
    ]

    PAYMENT_METHODS = [
        (
            "cash",
            "Cash"
        ),
        (
            "card",
            "Card"
        ),
        (
            "online",
            "Online"
        ),
    ]

    PAYMENT_STATUS_CHOICES = [
        (
            "unpaid",
            "Unpaid"
        ),
        (
            "paid",
            "Paid"
        ),
    ]

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    table = models.ForeignKey(
        Table,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    customer_name = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    customer_phone = models.CharField(
        max_length=30,
        blank=True,
        default=""
    )

    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPES,
        default="dine_in"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default="cash"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid"
    )

    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    service_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    change_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = [
            "-created_at"
        ]

    def __str__(self):

        return f"Order #{self.id}"


# =========================================================
# ORDER ITEM
# =========================================================

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name="order_items"
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):

        return (
            f"{self.menu_item.name} "
            f"x {self.quantity}"
        )

    def get_total(self):

        return (
            self.price *
            self.quantity
        )


# =========================================================
# INGREDIENT
# =========================================================

class Ingredient(models.Model):

    UNIT_CHOICES = [
        (
            "kg",
            "Kilogram"
        ),
        (
            "g",
            "Gram"
        ),
        (
            "liter",
            "Liter"
        ),
        (
            "ml",
            "Milliliter"
        ),
        (
            "piece",
            "Piece"
        ),
        (
            "pack",
            "Pack"
        ),
    ]

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="ingredients"
    )

    name = models.CharField(
        max_length=150
    )

    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default="piece"
    )

    current_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    minimum_stock = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "branch",
                    "name"
                ],
                name="unique_ingredient_name_per_branch"
            )
        ]

        ordering = [
            "name"
        ]

    def __str__(self):

        return self.name

    @property
    def is_low_stock(self):

        return (
            self.current_stock <=
            self.minimum_stock
        )

    @property
    def is_out_of_stock(self):

        return (
            self.current_stock <= 0
        )


# =========================================================
# STOCK IN
# =========================================================

class StockIn(models.Model):

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="stock_entries"
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    supplier = models.CharField(
        max_length=150,
        blank=True,
        default=""
    )

    note = models.TextField(
        blank=True,
        default=""
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return (
            f"{self.ingredient.name} "
            f"- {self.quantity} "
            f"{self.ingredient.unit}"
        )

    @property
    def total_cost(self):

        return (
            self.quantity *
            self.unit_price
        )

    def save(
        self,
        *args,
        **kwargs
    ):

        is_new = self.pk is None

        super().save(
            *args,
            **kwargs
        )

        if is_new:

            ingredient = self.ingredient

            ingredient.current_stock += (
                self.quantity
            )

            ingredient.save(
                update_fields=[
                    "current_stock"
                ]
            )


# =========================================================
# STOCK USAGE
# =========================================================

class StockUsage(models.Model):

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="usage_entries"
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    reason = models.CharField(
        max_length=200,
        blank=True,
        default=""
    )

    note = models.TextField(
        blank=True,
        default=""
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):

        return (
            f"{self.ingredient.name} "
            f"- {self.quantity} "
            f"{self.ingredient.unit}"
        )

    def save(
        self,
        *args,
        **kwargs
    ):

        if self.pk is None:

            ingredient = self.ingredient

            ingredient.current_stock -= (
                self.quantity
            )

            ingredient.save(
                update_fields=[
                    "current_stock"
                ]
            )

        super().save(
            *args,
            **kwargs
        )


# =========================================================
# MENU ITEM INGREDIENT / RECIPE
# =========================================================

class MenuItemIngredient(models.Model):

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="ingredients"
    )

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="menu_items"
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "menu_item",
                    "ingredient"
                ],
                name="unique_ingredient_per_menu_item"
            )
        ]

    def __str__(self):

        return (
            f"{self.menu_item.name} - "
            f"{self.ingredient.name} "
            f"({self.quantity} "
            f"{self.ingredient.unit})"
        )