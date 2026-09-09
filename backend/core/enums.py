from enum import Enum


class IntentType(str, Enum):
    INFORMATION = "INFORMATION"
    GUIDANCE = "GUIDANCE"
    SOLUTION = "SOLUTION"
    COMPLAINT = "COMPLAINT"
    COMPLAINT_STATUS = "COMPLAINT_STATUS"


class CategoryType(str, Enum):
    WATER = "WATER"
    AIR = "AIR"
    WASTE = "WASTE"


class ScopeType(str, Enum):
    CAMPUS = "CAMPUS"
    CITY = "CITY"


class ConversationPhase(str, Enum):
    GUIDANCE = "GUIDANCE"
    RESOLUTION_CHECK = "RESOLUTION_CHECK"
    COMPLAINT_OFFER = "COMPLAINT_OFFER"
    DETAIL_COLLECTION = "DETAIL_COLLECTION"
    COMPLAINT_CONFIRM = "COMPLAINT_CONFIRM"
    COMPLETE = "COMPLETE"


class ComplaintStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
