# GEE Data Fetcher

This script automate the process of retrieving spatial data from sentinel 2
satellites using Google Earth Engine. All the computing is done on the GEE
infrastructure, then images are brought back locally using the Google Drive API.
This work is the result of a collaboration between [INSIGHT](https://insight.nc)
and the University of New Caledonia through a PhD thesis.

## Environment and Python dependencies

The Python environment is managed with pixi. It's a cross-platform package
management tool that install libraries and applications in a reproducible way
(using conda environments).

Please follow the instruction of pixi's documentation to install it
(https://pixi.sh/latest/).

Once pixi is installed you can initialize the conda environment and install the
dependencies with:

```bash
# cd into the project root directory
pixi install
```

## Initialize Google Earth Engine API

1) Create a service account for Google Earth Engine
  - https://developers.google.com/earth-engine/guides/service_account
2) Add the Google Drive API access for the service account
  - https://console.cloud.google.com/apis/library/drive.googleapis.com

## Run the program

For example, the following command process the NBR from April to November
(included) for each year between 2017 and 2021.

```bash
pixi run cmd
  --aoi shape.gpkg
  --start 2017-04-01
  --end 2021-12-01
  --output directory
  --ee-credentials credentials.json
  --indices NBR
  --period-size 7M
  --period-frequency Y
```

## How to add a remote sensing indice?

If you want to add a remote sensing indice, you can add a function inside the dictionary
(`INDICE_FUNCTIONS`) located in the [sentinel2.py](https://github.com/etiennetack/gee-data-fetcher/blob/main/gee_data_fetcher/sentinel2.py) file:

```python
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
    ...
}
```
