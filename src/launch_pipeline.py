from pathlib import Path

from src.data_parsers.kudago_parser import parse_kudago_json
from src.vdb import wait_for_weaviate, create_collection_if_not_exists, load_events_to_weaviate
from src.utils.paths import DATA
import warnings


warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)

file_paths = [
    Path(DATA / "raw_data/real_events_data/events_pydantic_msk_20251212_130919.json"),
    Path(DATA / "raw_data/real_events_data/events_pydantic_spb_20251212_131151.json"),
]


def launch_pipeline():
    wait_for_weaviate()
    create_collection_if_not_exists()
    for file_path in file_paths:
        print(f"Parsing file: {file_path}")
        events = parse_kudago_json(file_path, owner="all")
        print(f"Loaded {len(events)} events")
        print(f"Loading events to Weaviate")
        load_events_to_weaviate(events, batch_size=100, verbose=True)
