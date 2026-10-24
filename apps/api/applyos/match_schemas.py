from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.matching.engine import MATCH_WEIGHTS, PRIORITY_WEIGHTS


class ScoringInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    weights: dict[str, int]
    priority_weights: dict[str, int]

    @field_validator("weights")
    @classmethod
    def weights_valid(cls, value):
        return cls.validate_weights(value, MATCH_WEIGHTS)

    @field_validator("priority_weights")
    @classmethod
    def priorities_valid(cls, value):
        return cls.validate_weights(value, PRIORITY_WEIGHTS)

    @staticmethod
    def validate_weights(value, expected):
        if (
            set(value) != set(expected)
            or any(not 0 <= x <= 100 for x in value.values())
            or sum(value.values()) != 100
        ):
            raise ValueError("Provide all component weights totaling 100.")
        return value
