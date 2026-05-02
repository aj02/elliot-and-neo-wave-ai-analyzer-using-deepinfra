# Sample CSVs

Land at Step 12. This directory will hold 3–4 NIFTY CSVs at different timeframes
(daily, weekly, 4h, 1h) for users to try the upload flow without supplying their
own data.

CSV schema (strict):

| column   | type     | notes                                          |
| -------- | -------- | ---------------------------------------------- |
| datetime | ISO 8601 | parseable, monotonic, no duplicates            |
| open     | float    |                                                |
| high     | float    | must be ≥ max(open, close)                     |
| low      | float    | must be ≤ min(open, close)                     |
| close    | float    |                                                |
| volume   | int      | may be 0 if the source doesn't provide volume  |
