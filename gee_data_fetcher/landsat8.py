# -*- coding: utf-8 -*-
import ee
import pendulum


def get_cloudless_images(
    bounds: ee.FeatureCollec,
    period: pendulum.Period,
) -> ee.ImageCollection:
    """Return a cloudless landsat image over the given bounds and period."""
    l8 = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")
    qa = l8.select("pixel_qa")
    return (
        l8.filterBounds(bounds)
        .filterDate(period.start.to_date_string(), period.end.to_date_string())
        .map(
            lambda image: image.updateMask(
                qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 5).eq(0))
            )
            .divide(10000)
            .copyProperties(image, ["system:time_start"])
        )
    )
