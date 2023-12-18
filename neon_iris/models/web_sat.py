"""API data models for the WebSAT API."""
from typing import Optional
from pydantic import BaseModel

class UserInput(BaseModel):
    """UserInput is the input data model for the WebSAT API."""
    utterance: Optional[str] = ""
    audio_input: Optional[str] = ""
    session_id: str = "websat0000"

class UserInputResponse(BaseModel):
    """UserInputResponse is the response data model for the WebSAT API."""
    utterance: Optional[str] = ""
    audio_output: Optional[str] = ""
    session_id: str = "websat0000"
    transcription: str
