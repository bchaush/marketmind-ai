from data_layer.census_api import fetch_census_demographics


def main() -> None:
    query = {
        "lat": 42.3505,
        "lng": -71.1054,
    }
    result = fetch_census_demographics(query)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
