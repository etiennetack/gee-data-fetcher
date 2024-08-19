# -*- coding: utf-8 -*-
from pathlib import Path

import click
import geopandas as gpd
from tqdm import tqdm

import ee_helper
import sentinel2
from drive_helper import GoogleDriveHelper
from dates_functions import iter_periods


@click.command()
@click.option(
    "--ee-credentials",
    type=str,
    required=True,
    help="Google Earth Engine credentials (service account credentials as JSON, do not forget to activate the Google Drive API!)",
)
@click.option("--aoi", type=str, required=True, help="Area of interest")
@click.option("--splited-aoi", is_flag=True, help="Splited Area of interest")
@click.option("--start", type=str, required=True, help="Start date")
@click.option("--end", type=str, default="now", help="End date (default: now)")
@click.option("--period-size", type=str, default="1M", help="Period size (default: 1M)")
@click.option("--period-frequency", type=str, help="Period frequency")
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
@click.option("--res", type=float, default=10.0, help="Resolution (default: 10.0)")
@click.option("--output", type=str, required=True, help="Output directory")
@click.option(
    "--cloud-score-threshold",
    type=float,
    default=0.65,
    help=(
        "Cloud score threshold (default: 0.65), "
        "see https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_CLOUD_SCORE_PLUS_V1_S2_HARMONIZED"
    ),
)
@click.option(
    "--count-band",
    is_flag=True,
    help="Export a band that counts the number of images for each pixel (excluding masked areas)",
)
@click.option(
    "--aggr-fn",
    type=str,
    default="median",
    help="The function used to aggretage every images",
)
def main(
    ee_credentials,
    aoi,
    splited_aoi,
    start,
    end,
    period_size,
    period_frequency,
    indices,
    bands,
    res,
    output,
    cloud_score_threshold,
    count_band,
    aggr_fn,
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

    # Create output directory
    output = Path(output)
    output.mkdir(exist_ok=True, parents=True)

    # Load area of interest
    aoi = Path(aoi)
    if not aoi.exists():
        raise FileNotFoundError(f"Area of interest {aoi} does not exist.")
    else:
        aoi = gpd.read_file(aoi).to_crs("EPSG:4326")

    # Images to export
    exports = {}

    # Process each month
    for period in iter_periods(start, end, period_size, period_frequency):
        period_start_str = period.start.to_date_string()
        period_end_str = period.end.to_date_string()

        print(f"Preparing period {period_start_str} -> {period_end_str}...")

        # Get cloudless images
        s2_images = sentinel2.get_cloudless_images(aoi, period, cloud_score_threshold)

        if ee_helper.empty_collection(s2_images):
            print("No images found, skipping...")
            continue

        # Compute median composite and clip to AOI
        composite = None
        if aggr_fn == "median":
            composite = s2_images.median()
        elif aggr_fn == "mean":
            composite = s2_images.mean()
        else:
            raise Exception(f"This aggregation function is not supported: {aggr_fn}")
        composite = ee_helper.clip_to_aoi(composite, aoi)

        # Prepare images to export
        for n, bounds in enumerate(
            # If splited_aoi is True, then do one iteration for each geometry
            [g.bounds for g in aoi.geometry]
            if splited_aoi
            # else do one iteration with the total bounds
            else [aoi.total_bounds]
        ):
            aoi_suffix = f"_{n}" if splited_aoi else ""
            if splited_aoi:
                print(f"Processing AOI {n + 1} of {len(aoi.geometry)}...")

            # Prepare indices
            if indices:
                for indice in indices.split(","):
                    name = f"{indice}_{period_start_str}_{period_end_str}{aoi_suffix}"
                    image = ee_helper.apply_indice_function(composite, indice)
                    exports[name] = image
                    print(f"[+] {indice}")

            # Prepare bands
            if bands:
                for band in bands.split(","):
                    name = f"{band}_{period_start_str}_{period_end_str}{aoi_suffix}"
                    image = sentinel2.get_band(composite, band)
                    exports[name] = image
                    print(f"[+] {band}")

            # Prepare count band
            if count_band:
                name = f"COUNT_{period_start_str}_{period_end_str}{aoi_suffix}"
                image = ee_helper.make_count_band(s2_images)
                image = image.clip(ee_helper.shapely_bounds_to_ee_geometry(bounds))
                exports[name] = image
                print("[+] COUNT")

    # Export images
    print("Exporting images...")
    for name, image in tqdm(exports.items()):
        # Update tqdm description
        tqdm.write(f"Exporting {name}...")
        # Export images to Google Drive from Earth Engine
        export_task = ee_helper.export_to_drive(image, name, bounds, res)
        ee_helper.run_task(export_task)
        # Download images from Google Drive and delete them
        for item in drive_helper.search(name):
            drive_helper.download_file(item, output / item.title)
            drive_helper.delete_file(item)

        # TODO ajouter commande pour clean le compte drive associé

    # Clean google drive
    for item in drive_helper.search("GEE"):
        drive_helper.delete_file(item)


if __name__ == "__main__":
    main()
