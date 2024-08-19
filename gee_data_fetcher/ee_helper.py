# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path
from typing import Callable, Dict, Iterable

import ee
import geopandas as gpd
import shapely as shp

import sentinel2

__all__ = [
    "clip_to_aoi",
    "ee_init",
    "export_to_drive",
    "gdf_to_ee_feature_collection",
    "image_is_empty",
    "resample",
    "run_task",
    "shapely_to_ee_multipolygon",
    "shapely_to_ee_polygon",
]


# Earth Engine helpers


def ee_init(credentials_file: Path) -> None:
    """Initialize Google Earth Engine."""
    with open(credentials_file, "r") as f:
        service_account = json.load(f)["client_email"]
    credentials = ee.ServiceAccountCredentials(
        service_account, credentials_file.as_posix()
    )
    ee.Initialize(credentials)


def resample(
    image: ee.Image,
    band: str,
    scale: int,
    resample_fn: str = "bilinear",
) -> ee.Image:
    """Resample a band to a given scale."""
    b = image.select(band)
    return (
        b.resample(resample_fn)
        .reproject(crs=b.projection().getInfo().get("crs"), scale=scale)
        .rename(f"{band}_{scale}m")
    )


def clip_to_aoi(image: ee.Image, aoi: gpd.GeoDataFrame) -> ee.Image:
    """Clip an image to an area of interest."""
    return image.clip(gdf_to_ee_feature_collection(aoi))


def export_to_drive(
    image: ee.Image,
    name: str,
    bounds: Iterable[float],
    res: float = 10.0,
) -> ee.batch.Task:
    """Export an image to Google Drive"""
    projection = image.projection().getInfo()
    return ee.batch.Export.image.toDrive(
        image=image,
        description=name,
        folder="GEE",
        region=shapely_bounds_to_ee_geometry(bounds),
        scale=res,
        crs=projection.get("crs"),
        formatOptions={"cloudOptimized": True},
        maxPixels=1e13,
    )


def run_task(
    task: ee.batch.Task,
    update_time: int = 10,
    delay_time: int = 30,
    max_retry: int = 10,
) -> None:
    """Run an Earth Engine task."""
    try:
        task.start()
        while task.status().get("state") not in ["COMPLETED", "FAILED"]:
            time.sleep(update_time)
        if task.status().get("state") == "FAILED":
            raise Exception("Task failed.")
    except:  # noqa: E722 # catch all exceptions
        if max_retry > 0:
            time.sleep(delay_time)
            run_task(task, update_time, delay_time * 2, max_retry - 1)
        else:
            raise RuntimeError(f"Task {task.status().get('description')} failed.")


def empty_collection(collection: ee.ImageCollection) -> bool:
    """Return True if the collection is empty."""
    return collection.size().getInfo() == 0


def image_is_empty(image: ee.Image) -> bool:
    """Return True if the image is empty."""
    return image.getInfo().get("bands") is None


def make_count_band(collection: ee.ImageCollection, band: str = "B2") -> ee.Image:
    """Create a count band that display the number of images used for each pixel."""
    return collection.select(band).count().unmask(0).rename("COUNT")


def apply_indice_function(
    image: ee.Image,
    indice: str,
    functions: Dict[str, Callable[ee.Image, ee.Image]] = sentinel2.INDICE_FUNCTIONS,
) -> ee.Image:
    """Apply an indice function to an image."""
    if indice not in functions:
        raise NotImplementedError(f"Indice {indice} not implemented.")
    return functions[indice](image)


# Converters
def shapely_to_ee_point(point: shp.Point) -> ee.Geometry.Point:
    """Convert a Shapely point to an Earth Engine point."""
    return ee.Geometry.Point(point.coords)


def shapely_to_ee_polygon(polygon: shp.Polygon) -> ee.Geometry.Polygon:
    """Convert a Shapely polygon to an Earth Engine polygon."""
    return ee.Geometry.Polygon(list(polygon.exterior.coords))


def shapely_to_ee_multipolygon(
    multipolygon: shp.MultiPolygon,
) -> ee.Geometry.MultiPolygon:
    """Convert a Shapely multipolygon to an Earth Engine multipolygon."""
    return ee.Geometry.MultiPolygon(
        [shapely_to_ee_polygon(polygon) for polygon in multipolygon.geoms]
    )


def shapely_to_ee_geometry(shape: shp.Geometry) -> ee.Geometry:
    """Convert a Shapely polygon or multipolygon to an Earth Engine polygon or multipolygon."""
    if isinstance(shape, shp.Polygon):
        return shapely_to_ee_polygon(shape)
    elif isinstance(shape, shp.MultiPolygon):
        return shapely_to_ee_multipolygon(shape)
    elif isinstance(shape, shp.Point):
        return shapely_to_ee_point(shape)
    else:
        raise NotImplementedError(
            f"Shape conversion to EE not implemented for {type(shape)}."
        )


def shapely_bounds_to_ee_geometry(bounds: Iterable[float]) -> ee.Geometry:
    """Convert a Shapely bounds to an Earth Engine geometry."""
    if len(bounds) != 4:
        raise ValueError("Bounds must be a list of 4 elements.")
    return shapely_to_ee_geometry(shp.box(*bounds))


def gdf_to_ee_feature_collection(gdf: gpd.GeoDataFrame) -> ee.FeatureCollection:
    """Convert a GeoDataFrame to an Earth Engine FeatureCollection."""
    return ee.FeatureCollection(
        [
            ee.Feature(
                shapely_to_ee_geometry(row.get("geometry")),
                row.drop("geometry").to_dict(),
            )
            for _, row in gdf.iterrows()
        ]
    )
