# Google Calendar Prayer Times

A script that fetches the Islamic prayer times from [prayer-times-api.izaachen.de](https://prayer-times-api.izaachen.de) and creates current months' prayer times in a specific Google Calendar using Google's Service Account crendentials.

Follow the this [guide](./docs/Google_Calendar_API_Service_Account.md) to generate the credentials, and create a `.env` file based on the sample.

> **Note:** This script was tested and used with Python 3.12

Preview:

![Calendar Screenshot](./docs/calendar-screenshot.png)

## Run

Install dependencies:

```shell
pip install -r requirements.txt
```

Run the script:

```shell
python src/script.py
```

## Development

Format:

```shell
make format
```

Lint:

```shell
make lint
```
