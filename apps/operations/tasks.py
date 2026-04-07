"""
Celery tasks for operations module.
Handles background jobs like reorder alerts, stock management, etc.
"""
import logging
from django.db import transaction
from django.db.models import F, Q

from apps.operations.models import Product
from apps.notifications.models import Notification
from utils.tasks import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_reorder_levels(self):
    """
    Periodic task to check stock levels and create alerts for products below reorder level.
    Run every X minutes via Celery Beat.

    Optimized query:
    - Uses select_related for workspace
    - Filters products where stock <= reorder_level
    - Groups by workspace to avoid duplicate notifications
    """
    try:
        # Get all products below reorder level, optimized query
        low_stock_products = (
            Product.objects
            .filter(Q(stock_on_hand__lte=F("reorder_level")) & Q(is_active=True))
            .select_related("workspace")
            .values_list("workspace_id", "pk", "sku", "name", "stock_on_hand", "reorder_level")
            .distinct()
        )

        if not low_stock_products:
            logger.info("No products below reorder level")
            return "No products below reorder level."

        for workspace_id, product_id, sku, name, available, reorder in low_stock_products:
            notification = Notification(
                workspace_id=workspace_id,
                title="Low Stock Alert",
                message=f"Product {sku} ({name}) is below reorder level. Current: {available}, Minimum: {reorder}",
                notification_type=Notification.Type.ALERT,
                is_read=False,
            )
            notification.save()

        logger.info(f"Reorder alerts: created {len(low_stock_products)} alerts")
        return f"Checked reorder levels. Created {len(low_stock_products)} alerts."

    except Exception as e:
        logger.error(f"Reorder level check failed: {str(e)}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60)



@shared_task(max_retries=3)
def validate_stock_integrity():
    """
    Periodic integrity check to ensure no product has negative stock.
    Runs daily to detect and log any constraint violations.
    """
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            # Check for negative stock (should not happen with DB constraints)
            cursor.execute("""
                SELECT id, sku, name, stock_on_hand, reserved_quantity
                FROM operations_product
                WHERE stock_on_hand < 0 OR reserved_quantity < 0 OR reserved_quantity > stock_on_hand
            """)
            violations = cursor.fetchall()

        if violations:
            # Log violations for investigation
            violation_details = [
                f"Product {row[1]} (ID: {row[0]}): stock={row[3]}, reserved={row[4]}"
                for row in violations
            ]
            error_msg = f"Stock integrity violations detected:\n" + "\n".join(violation_details)
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info("Stock integrity check passed")
        return "Stock integrity check passed."

    except Exception as e:
        logger.error(f"Stock integrity check failed: {str(e)}", exc_info=True)
        raise



@shared_task(max_retries=2)
@transaction.atomic
def cleanup_expired_reservations():
    """
    Periodic task to clean up old stock reservations.
    Releases reservations from orders that are older than X days without being dispatched.
    Uses select_for_update to prevent race conditions.
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.operations.models import SalesOrder, StockReservation, StockReservationLine

    try:
        # Find old reservations (e.g., older than 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)

        # Optimize query: prefetch reservation lines and related products
        old_orders = (
            SalesOrder.objects
            .filter(
                status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.AWAITING_STOCK],
                created_at__lt=cutoff_date,
            )
            .select_related("stock_reservation")
            .prefetch_related("stock_reservation__lines__product")
        )

        count = 0
        for order in old_orders:
            try:
                reservation = order.stock_reservation

                # Lock product rows before updating
                product_ids = reservation.lines.values_list("product_id", flat=True)
                locked_products = {
                    p.pk: p for p in Product.objects.select_for_update().filter(pk__in=product_ids)
                }

                # Release all reservations with row-level locking
                for line in reservation.lines.all():
                    product = locked_products.get(line.product_id)
                    if product:
                        product.reserved_quantity = max(0, product.reserved_quantity - line.quantity_reserved)
                        product.save(update_fields=["reserved_quantity"])
                    line.delete()

                reservation.delete()
                count += 1
                logger.info(f"Released reservation for order {order.code}")
            except StockReservation.DoesNotExist:
                pass

        logger.info(f"Cleaned up {count} expired reservations")
        return f"Cleaned up {count} expired reservations."

    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        from celery import current_task
        if current_task.request.retries < current_task.max_retries:
            raise current_task.retry(exc=e, countdown=120)
        else:
            raise

