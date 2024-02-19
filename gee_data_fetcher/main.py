# -*- coding: utf-8 -*-
from pathlib import Path

import ee
import click
import pendulum
import geopandas as gpd
from enum import Enum
from tqdm import tqdm

import ee_helper
import sentinel2
from drive_helper import GoogleDriveHelper


def parse_period(period_size: str) -> (int, str):
    """Parse the period size and unit."""
    if len(period_size) < 2:
        if period_size[-1].isdigit():
            raise ValueError(
                f"Invalid period size format ({period_size[-1]} does not represent a valid period unit)."
            )

    period_unit = parse_period_unit(period_size[-1].lower())

    if len(period_size) == 1:
        period_size = 1
    elif period_size[:-1].isdigit():
        period_size = int(period_size[:-1])
    else:
        raise ValueError(
            f"Invalid period size format ({period_size[:-1]} is not a number)."
        )

    return period_size, period_unit


def parse_period_unit(period_unit: str) -> str:
    """Parse the period unit (small representation to full)."""
    if period_unit == "d":
        return "days"
    elif period_unit == "w":
        return "weeks"
    elif period_unit == "m":
        return "months"
    elif period_unit == "y":
        return "years"
    else:
        raise ValueError(f"Invalid period unit: {period_unit}")


def get_period_end(
    period_start: pendulum.DateTime,
    period_unit: str,
    period_size: int,
) -> pendulum.DateTime:
    return (
        (
            period_start
            + pendulum.duration(**{period_unit: period_size})
            - pendulum.duration(days=1)
        )
        # go to the end of the day (i.e., 23:59:59.999999)
        .end_of("day")
    )


def make_period(
    period_start: pendulum.DateTime,
    period_unit: str,
    period_size: int,
) -> pendulum.Interval:
    return get_period_end(period_start, period_unit, period_size) - period_start


@click.command()
@click.option("--aoi", type=str, required=True, help="Area of interest")
@click.option("--splited-aoi", is_flag=True, help="Splited Area of interest")
@click.option("--start", type=str, required=True, help="Start date")
@click.option("--end", type=str, default="now", help="End date (default: now)")
@click.option("--period-size", type=str, default="1M", help="Period size (default: 1M)")
@click.option("--period-frequency", type=str, help="Period frequency")
@click.option("--output", type=str, required=True, help="Output directory")
@click.option(
    "--indices",
    type=str,
    default="",
    help="Indices to compute (comma separated)",
)
@click.option(
    "--bands",
    type=str,
    default="",
    help="Bands to download (comma separated)",
)
@click.option(
    "--ee-credentials",
    type=str,
    required=True,
    help="Google Earth Engine credentials (service account credentials as JSON, do not forget to activate the Google Drive API!)",
)
@click.option(
    "--cloud-score-threshold",
    type=float,
    default=0.65,
    help=(
        "Cloud score threshold (default: 0.65), "
        "see https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED"
    ),
)
@click.option("--res", type=float, default=10.0, help="Resolution (default: 10.0)")
@click.option(
    "--count-band",
    is_flag=True,
    help="Export a band that counts the number of images for each pixel (excluding masked areas)",
)
def main(
    aoi,
    splited_aoi,
    start,
    end,
    period_size,
    period_frequency,
    output,
    indices,
    bands,
    ee_credentials,
    cloud_score_threshold,
    res,
    count_band,
):
    """Download Sentinel-2 images from Google Earth Engine."""
    # Initialize Google Earth Engine
    ee_credentials = Path(ee_credentials)
    if not ee_credentials.exists():
        raise FileNotFoundError(
            f"Google Earth Engine credentials {ee_credentials} does not exist."
        )

    # Initialize Google APIs using the service account credentials
    ee_helper.ee_init(ee_credentials)
    drive_helper = GoogleDriveHelper(ee_credentials)

    # Load area of interest
    aoi = Path(aoi)
    if not aoi.exists():
        raise FileNotFoundError(f"Area of interest {aoi} does not exist.")
    else:
        aoi = gpd.read_file(aoi).to_crs("EPSG:4326")

    # Parse start and end dates
    # start = pendulum.parse(start).start_of("month")
    start = pendulum.parse(start)

    if end == "now":
        end = pendulum.now()
    else:
        end = pendulum.parse(end)

    # Create output directory
    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)

    # Parse period size
    period_size, period_unit = parse_period(period_size)
    if period_frequency is not None:
        period_frequency, period_frequency_unit = parse_period(period_frequency)
    else:
        period_frequency, period_frequency_unit = period_size, period_unit

    # Process each month
    for period_start in (
        pendulum.interval(start, end)
        #
        .range(period_frequency_unit, period_frequency)
    ):
        period = make_period(period_start, period_unit, period_size)

        period_start_str = period.start.to_date_string()
        period_end_str = period.end.to_date_string()

        print(f"Processing period {period_start_str} -> {period_end_str}...")

        # Get cloudless images
        s2_images = sentinel2.get_cloudless_images(aoi, period, cloud_score_threshold)

        if ee_helper.empty_collection(s2_images):
            print("No images found, skipping...")
            continue

        # Compute median composite and clip to AOI
        median_composite = ee_helper.clip_to_aoi(s2_images.median(), aoi)

        # Compute indices and download images
        for n, bounds in enumerate(
            # If splited_aoi is True, then do one iteration for each geometry
            [g.bounds for g in aoi.geometry]
            if splited_aoi
            # else do one iteration with the total bounds
            else [aoi.total_bounds]
        ):
            images = {}

            aoi_suffix = f"_{n}" if splited_aoi else ""

            # Prepare indices
            if indices:
                for indice in indices.split(","):
                    name = f"{indice}_{period_start_str}_{period_end_str}{aoi_suffix}"
                    image = ee_helper.apply_indice_function(median_composite, indice)
                    images[name] = image

            # Prepare bands
            if bands:
                for band in bands.split(","):
                    name = f"{band}_{period_start_str}_{period_end_str}{aoi_suffix}"
                    image = sentinel2.get_band(median_composite, band)
                    images[name] = image

            # Prepare count band
            if count_band:
                name = f"COUNT_{period_start_str}_{period_end_str}{aoi_suffix}"
                image = ee_helper.make_count_band(s2_images)
                image = image.clip(ee_helper.shapely_bounds_to_ee_geometry(bounds))
                images[name] = image

            for name, image in tqdm(images.items()):
                # Export images to Google Drive from Earth Engine
                export_task = ee_helper.export_to_drive(image, name, bounds, res)
                ee_helper.run_task(export_task)

                # Download images from Google Drive and delete them
                for item in drive_helper.search(name):
                    drive_helper.download_file(item, output / item.title)
                    drive_helper.delete_file(item)

    # Clean google drive
    for item in drive_helper.search("GEE"):
        drive_helper.delete_file(item)


if __name__ == "__main__":
    main()
