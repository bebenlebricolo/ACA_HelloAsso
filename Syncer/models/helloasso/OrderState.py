from enum import Enum

class OrderState(Enum) :
    Authorized = "Authorized"
    Waiting = "Waiting"
    Processed = "Processed"
    Registered = "Registered"
    Deleted = "Deleted"
    Unknown = "Unknown"
    Canceled = "Canceled"
    Refused = "Refused"
    Abandoned = "Abandoned"