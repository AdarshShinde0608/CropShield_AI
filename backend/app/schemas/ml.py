from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class ScorePreviewOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_threshold: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
