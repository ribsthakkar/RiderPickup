There are two parsers implemented in Avicena
* CSV
* LogistiCare

All parser modules must implement to the following function header:

`parse_trips_to_df(path_to_trips_file: str, merge_details:
Dict[str:MergeAddress], revenue_table: Dict[str:List[RevenueRate]],
output_directory: str) -> Pandas.DataFrame`

## CSV
The CSV Parser takes a CSV of input trips with the following header:
`date,trip_id,customer_name,trip_pickup_time,trip_pickup_name,trip_pickup_address,trip_dropoff_time,trip_dropoff_name,trip_dropoff_address,trip_los,trip_miles`
to produce the trip assignments.

## LogistiCare
This is a parser used to parse the PDFs from LogistiCare with its
proprietary formatting.

