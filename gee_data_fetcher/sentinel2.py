# -*- coding: utf-8 -*-
from typing import Callable, Dict, Tuple
import pendulum
import geopandas as gpd
import ee
import ee_helper

__all__ = [
    "INDICE_FUNCTIONS",
    "get_cloudless_images",
    "get_band",
]

INDICE_FUNCTIONS: Dict[str, Callable[[ee.Image], ee.Image]] = {
    "NDVI": (
        # -1.0 - 1.0: clouds, show, water
        # near 0.0: barren rock, sand
        # 0.0 - 0.1: empty areas of rock, sand, or snow
        # 0.2 - 0.3: shrub and grassland
        # 0.6 - 0.8: temperate and tropical forests
        lambda image: image.normalizedDifference(["B8", "B4"])
        #
        .rename("NDVI")
    ),
    "NDWIv": (
        # Gao, Bo-Cai (1996)
        # => NDMI
        # -1 - 0: bright surface with no vegetation or water content
        # 1: represent water content
        # https://en.wikipedia.org/wiki/Normalized_difference_water_index (2024-01-22)
        lambda image: image.addBands(ee_helper.resample(image, "B11", 10))
        .normalizedDifference(["B8", "B11_10m"])
        .rename("NDWIv")
    ),
    "NDWIw": (
        # McFeeters, Stuart K. (1996)
        # 0.2 - 1.0: water surface
        # 0.0 - 0.2: flooding, humid soil
        # -0.3 - 0.0: arid soil
        # -1.0 - -0.3: barren rock
        lambda image: image.normalizedDifference(["B3", "B8"])
        #
        .rename("NDWIw")
    ),
    # "NDMI": (
    #     # -1 – -0.8 Bare soil,
    #     # -0.8 – -0.6 Almost absent canopy cover,
    #     # -0.6 – -0.4 Very low canopy cover,
    #     # -0.4 – -0.2 Low canopy cover, dry or very low canopy cover, wet,
    #     # -0.2 – 0 Mid-low canopy cover, high water stress or low canopy cover, low water stress,
    #     # 0 – 0.2 Average canopy cover, high water stress or mid-low canopy cover, low water stress,
    #     # 0.2 – 0.4 Mid-high canopy cover, high water stress or average canopy cover, low water stress,
    #     # 0.4 – 0.6 High canopy cover, no water stress,
    #     # 0.6 – 0.8 Very high canopy cover, no water stress,
    #     # 0.8 – 1 Total canopy cover, no water stress/waterlogging
    #     lambda image: image.addBands(ee_helper.resample(image, "B11", 10))
    #     .normalizedDifference(["B8", "B11_10m"])
    #     .rename("NDMI")
    # ),
    "Redness": (
        # Document the redness index
        # https://gis.stackexchange.com/questions/302992/what-is-the-redness-index
        lambda image: image.addBands(ee_helper.resample(image, "B5", 10))
        .normalizedDifference(["B5_10m", "B3"])
        .rename("RI")
    ),
    "NBR": (
        # Normalized Burn Ratio
        # https://docs.digitalearthafrica.org/en/latest/sandbox/notebooks/Real_world_examples/Burnt_area_mapping.html
        lambda image: image.addBands(ee_helper.resample(image, "B12", 10))
        .normalizedDifference(["B8", "B12_10m"])
        .rename("NBR")
    ),
    "Brightness": (
        # TODO À vérifier
        lambda image: image.expression(
            # https://foodsecurity-tep.net/node/210
            # "sqrt(((Red * Red) / (Green * Green)) / 2)",
            "sqrt(((RED * RED) + (NIR * NIR)))",
            {
                "Red": image.select("B4"),
                "Green": image.select("B8"),
            },
        ).rename("BI")
    ),
}


def get_cloudless_images(
    bounds: gpd.GeoDataFrame,
    period: pendulum.Interval,
    cloud_score_threshold: float = 0.65,
) -> ee.ImageCollection:
    """Return a cloudless sentinel-2 image over the given bounds and period."""
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    cs_plus = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    ee_bounds = ee_helper.shapely_bounds_to_ee_geometry(bounds.total_bounds)
    return (
        s2.filterBounds(ee_bounds)
        .filterDate(period.start.to_date_string(), period.end.to_date_string())
        .linkCollection(cs_plus, "cs_cdf")
        .map(
            lambda image: image.updateMask(
                image.select("cs_cdf").gte(cloud_score_threshold)
            )
        )
    )


def get_band(image: ee.Image, band: str) -> ee.Image:
    """Return the band of the image and scale."""
    if band in [
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "B6",
        "B7",
        "B8",
        "B8A",
        "B9",
        "B11",
        "B12",
    ]:
        return image.select(band).multiply(0.0001).toFloat()

    if band in [
        "WVP",
        "AOT",
    ]:
        return image.select(band).multiply(0.001).toFloat()

    if band in [
        "SCL",
        "TCI_R",
        "TCI_G",
        "TCI_B",
        "MSK_CLDPRB",
        "MSK_SNWPRB",
        "QA10",
        "QA20",
        "QA60",
    ]:
        return image.select(band)
