import argparse
import logging
import os
import time
from pathlib import Path

from . import pd

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())

logger = logging.getLogger(__name__)


def positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def duration_seconds(minutes):
    return minutes * 60


def load_env_file(path):
    """Read simple KEY=VALUE entries from a dotenv-format file."""
    values = {}
    with Path(path).open(encoding="utf-8") as env_file:
        for line_number, line in enumerate(env_file, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line.removeprefix("export ").lstrip()
            if "=" not in line:
                raise ValueError(f"{path}:{line_number} must use KEY=VALUE format")
            key, value = line.split("=", maxsplit=1)
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError(f"{path}:{line_number} has an empty key")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="pagerduty-auto-ack",
        description="Monitor and automatically ACKnowledge PagerDuty incidents",
    )

    parser.add_argument(
        "--pagerduty-api-key",
        help="PagerDuty user API key",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="PATH",
        help="dotenv file to load (defaults to .env when present)",
    )
    parser.add_argument(
        "--interval",
        required=False,
        type=positive_int,
        default=60,
        help="how often (in seconds) to run the check",
    )
    parser.add_argument(
        "--urgency",
        required=False,
        choices=["high", "low"],
        action="append",
        default=[],
        dest="urgencies",
        help="defaults to all urgencies",
    )
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--once",
        action="store_true",
        help="check and acknowledge incidents once, then exit",
    )
    run_mode.add_argument(
        "--duration",
        type=positive_int,
        metavar="MINUTES",
        help="run checks for this many minutes, then exit",
    )

    args = parser.parse_args(argv)
    env_values = {}
    env_path = Path(args.env_file)
    if env_path.is_file():
        try:
            env_values = load_env_file(env_path)
        except (OSError, ValueError) as error:
            parser.error(str(error))

    args.pagerduty_api_key = (
        args.pagerduty_api_key
        or os.environ.get("PAGERDUTY_API_KEY")
        or env_values.get("PAGERDUTY_API_KEY")
    )
    if not args.pagerduty_api_key:
        parser.error(
            "--pagerduty-api-key, PAGERDUTY_API_KEY, or PAGERDUTY_API_KEY in .env is required"
        )
    return args


def acknowledge_current_incidents(pd_client, user_id, urgencies):
    incidents = pd.get_triggered_incidents(
        pd_client, user_ids=[user_id], urgencies=urgencies
    )
    incident_ids = [incident["id"] for incident in incidents]
    acknowledged = pd.acknowledge_incidents(pd_client, incident_ids)
    logger.info("Incidents acknowledged: %s", len(acknowledged))
    return acknowledged


def main():
    args = parse_args()

    pd_api_key = args.pagerduty_api_key

    ack_incidents = []
    try:
        with pd.get_client(pd_api_key) as pd_client:
            user = pd.get_current_user(pd_client)
            user_email = user.get("email")
            user_id = user.get("id")

            logger.info(f"Running as user: {user_email}")

            deadline = (
                time.monotonic() + duration_seconds(args.duration)
                if args.duration is not None
                else None
            )
            while True:
                ack_incidents += acknowledge_current_incidents(
                    pd_client, user_id, args.urgencies
                )
                if args.once:
                    return

                sleep_for = args.interval
                if deadline is not None:
                    sleep_for = min(sleep_for, deadline - time.monotonic())
                    if sleep_for <= 0:
                        return
                logger.debug(f"Sleeping for {args.interval} seconds")
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        count = len(ack_incidents)
        logger.info(f"Acknowledged {count} incidents")
        print("You can find a list of acknowledged incidents below:")
        for incident in ack_incidents:
            print(
                "#{0} {1}".format(
                    incident.get("incident_number"), incident.get("html_url")
                )
            )


if __name__ == "__main__":
    main()
