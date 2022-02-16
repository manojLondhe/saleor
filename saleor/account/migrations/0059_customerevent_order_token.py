# Generated by Django 3.2.12 on 2022-02-16 13:10

from django.db import migrations, models

BATCH_SIZE = 10000


def save_order_tokens(apps, schema_editor):
    CustomerEvent = apps.get_model("account", "CustomerEvent")
    Order = apps.get_model("order", "Order")

    queryset = CustomerEvent.objects.filter(order_id__isnull=False)
    for batch_pks in queryset_in_batches(queryset):
        batch = CustomerEvent.objects.filter(pk__in=batch_pks)
        order_ids = batch.values_list("order_id", flat=True)
        order_id_to_token = {
            id: token
            for id, token in Order.objects.filter(id__in=order_ids).values_list(
                "id", "token"
            )
        }
        for event in batch:
            event.order_token = order_id_to_token.get(event.order_id)

        CustomerEvent.objects.bulk_update(batch, ["order_token"])


def queryset_in_batches(queryset):
    """Slice a queryset into batches.

    Input queryset should be sorted be pk.
    """
    start_pk = 0

    while True:
        qs = queryset.filter(pk__gt=start_pk)[:BATCH_SIZE]
        pks = list(qs.values_list("pk", flat=True))

        if not pks:
            break

        yield pks

        start_pk = pks[-1]


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0058_update_user_search_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="customerevent",
            name="order_token",
            field=models.UUIDField(null=True),
        ),
        # move order relation to order_token field
        migrations.RunPython(save_order_tokens, migrations.RunPython.noop),
        # remove order relation
        migrations.RemoveField(
            model_name="customerevent",
            name="order",
        ),
    ]