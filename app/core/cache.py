# This file will contain caching logic for osmnx graphs.
#
# By default, osmnx caches downloads in a `cache` directory.
# We might want more advanced logic here in the future, such as:
# - A time-based cache (e.g., refresh data every week)
# - Storing pre-processed graphs in a database or a file store like Redis
#   to avoid having to build the graph from raw data on every startup.

def configure_osmnx_caching():
    """Sets up osmnx caching settings."""
    import osmnx as ox
    # Example: configure osmnx to use a specific directory and log progress
    ox.config(
        cache_folder="./osmnx_cache",
        log_console=True,
        use_cache=True
    )
    print("osmnx caching configured.")

# You would call this function at the startup of your FastAPI app.
