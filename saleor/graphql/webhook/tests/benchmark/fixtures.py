import pytest

from .....app.models import App
from .....webhook.event_types import WebhookEventAsyncType, WebhookEventSyncType
from .....webhook.models import Webhook, WebhookEvent

NUMBER_OF_WEBHOOKS_PER_APP = 6


def _prepare_webhook_events(option, webhook):
    webhook_events = []

    if option == 0:
        webhook_events.extend(
            [
                WebhookEvent(
                    webhook=webhook, event_type=WebhookEventSyncType.PAYMENT_AUTHORIZE
                ),
                WebhookEvent(webhook=webhook, event_type=WebhookEventAsyncType.ANY),
            ]
        )

    elif option == 1:
        webhook_events.append(
            WebhookEvent(
                webhook=webhook,
                event_type=WebhookEventSyncType.ORDER_FILTER_SHIPPING_METHODS,
            ),
        )

    elif option == 2:
        webhook_events.append(
            WebhookEvent(
                webhook=webhook, event_type=WebhookEventAsyncType.CHANNEL_CREATED
            ),
        )

    return webhook_events


def _prepare_app_webhooks(index, app):
    webhooks = []
    webhook_events = []

    for webhook_index in range(index % 4):
        webhook = Webhook(
            name=f"Webhook_{index}",
            app=app,
            target_url=f"http://localhost/test_{webhook_index}",
            is_active=webhook_index % 2,
        )
        webhooks.append(webhook)

        webhook_events.extend(_prepare_webhook_events(webhook_index % 4, webhook))

    return webhooks, webhook_events


@pytest.fixture
def webhook_events(db):
    apps = App.objects.bulk_create(
        [
            App(name="App1", is_active=True),
            App(name="App2", is_active=False),
            App(name="App3", is_active=True),
            App(name="App4", is_active=False),
        ]
    )
    webhooks = []
    webhook_events = []

    for app in apps[:2]:
        for index in range(NUMBER_OF_WEBHOOKS_PER_APP):
            if not index % 3:
                continue

            app_webhooks, app_webhook_events = _prepare_app_webhooks(index, app)
            webhooks.extend(app_webhooks)
            webhook_events.extend(app_webhook_events)

    Webhook.objects.bulk_create(webhooks)
    WebhookEvent.objects.bulk_create(webhook_events)

    return webhook_events
