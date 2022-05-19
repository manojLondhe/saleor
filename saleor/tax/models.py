from django.conf import settings
from django.db import models
from django_countries.fields import CountryField

from ..channel.models import Channel
from ..core.models import ModelWithMetadata


class TaxClass(ModelWithMetadata):
    name = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ("is_default", "name")

    def __str__(self):
        return self.name


class TaxClassCountryRate(models.Model):
    tax_class = models.ForeignKey(
        TaxClass, related_name="country_rates", on_delete=models.CASCADE
    )
    country = CountryField()
    rate = models.DecimalField(
        max_digits=settings.DEFAULT_MAX_DIGITS,
        decimal_places=settings.DEFAULT_DECIMAL_PLACES,
    )

    class Meta:
        ordering = ("country",)
        unique_together = (("tax_class", "country"),)

    def __str__(self):
        return f"{self.country}: {self.rate}"


class TaxConfiguration(ModelWithMetadata):
    channel = models.OneToOneField(
        Channel, related_name="tax_configuration", on_delete=models.CASCADE
    )
    charge_taxes = models.BooleanField(default=True)
    display_gross_prices = models.BooleanField(default=True)
    prices_entered_with_tax = models.BooleanField(default=True)

    class Meta:
        ordering = ("channel",)


class TaxConfigurationPerCountry(models.Model):
    tax_configuration = models.ForeignKey(
        TaxConfiguration, related_name="country_exceptions", on_delete=models.CASCADE
    )
    country = CountryField()
    charge_taxes = models.BooleanField(default=True)
    display_gross_prices = models.BooleanField(default=True)

    class Meta:
        ordering = ("country",)
        unique_together = (("tax_configuration", "country"),)
