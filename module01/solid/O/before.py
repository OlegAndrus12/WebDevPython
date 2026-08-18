"""Open/Closed — BEFORE: every new delivery channel forces an edit to the `match` block inside
`Notifier.send`, so working code must be modified in order to add behaviour."""

from enum import Enum

class ServiceType(Enum):
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"

class Notifier:
    def send(self, message, service=ServiceType.EMAIL):
        match service:
            case ServiceType.EMAIL:
                print(f"Sending Email: {message}")
            case ServiceType.SMS:
                print(f"Sending SMS: {message}")
            case ServiceType.SLACK:
                print(f"Sending Slack: {message}")

message = "Black Friday is coming"

notifier = Notifier()
notifier.send(message, ServiceType.SLACK)
notifier.send(message, ServiceType.EMAIL)