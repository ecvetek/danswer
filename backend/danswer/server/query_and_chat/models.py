from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import root_validator

from danswer.chat.models import RetrievalDocs
from danswer.configs.constants import DocumentSource
from danswer.configs.constants import MessageType
from danswer.configs.constants import SearchFeedbackType
from danswer.db.enums import ChatSessionSharedStatus
from danswer.file_store.models import FileDescriptor
from danswer.llm.override_models import LLMOverride
from danswer.llm.override_models import PromptOverride
from danswer.search.models import BaseFilters
from danswer.search.models import ChunkContext
from danswer.search.models import RetrievalDetails
from danswer.search.models import SearchDoc
from danswer.search.models import Tag
from danswer.tools.models import ToolCallFinalResult


class SourceTag(Tag):
    source: DocumentSource


class TagResponse(BaseModel):
    tags: list[SourceTag]


class SimpleQueryRequest(BaseModel):
    query: str


class UpdateChatSessionThreadRequest(BaseModel):
    # If not specified, use Danswer default persona
    chat_session_id: int
    new_alternate_model: str


class ChatSessionCreationRequest(BaseModel):
    # If not specified, use Danswer default persona
    persona_id: int = 0
    description: str | None = None


class CreateChatSessionID(BaseModel):
    chat_session_id: int


class ChatFeedbackRequest(BaseModel):
    chat_message_id: int
    is_positive: bool | None = None
    feedback_text: str | None = None
    predefined_feedback: str | None = None

    @root_validator
    def check_is_positive_or_feedback_text(cls: BaseModel, values: dict) -> dict:
        is_positive, feedback_text = values.get("is_positive"), values.get(
            "feedback_text"
        )

        if is_positive is None and feedback_text is None:
            raise ValueError("Empty feedback received.")

        return values


"""
Currently the different branches are generated by changing the search query

                 [Empty Root Message]  This allows the first message to be branched as well
              /           |           \
[First Message] [First Message Edit 1] [First Message Edit 2]
       |                  |
[Second Message]  [Second Message of Edit 1 Branch]
"""


class CreateChatMessageRequest(ChunkContext):
    """Before creating messages, be sure to create a chat_session and get an id"""

    chat_session_id: int
    # This is the primary-key (unique identifier) for the previous message of the tree
    parent_message_id: int | None
    # New message contents
    message: str
    # Files that we should attach to this message
    file_descriptors: list[FileDescriptor]
    # If no prompt provided, uses the largest prompt of the chat session
    # but really this should be explicitly specified, only in the simplified APIs is this inferred
    # Use prompt_id 0 to use the system default prompt which is Answer-Question
    prompt_id: int | None
    # If search_doc_ids provided, then retrieval options are unused
    search_doc_ids: list[int] | None
    retrieval_options: RetrievalDetails | None
    # allows the caller to specify the exact search query they want to use
    # will disable Query Rewording if specified
    query_override: str | None = None

    # enables additional handling to ensure that we regenerate with a given user message ID
    regenerate: bool | None = None

    # allows the caller to override the Persona / Prompt
    # these do not persist in the chat thread details
    llm_override: LLMOverride | None = None
    prompt_override: PromptOverride | None = None

    # allow user to specify an alternate assistnat
    alternate_assistant_id: int | None = None

    # used for seeded chats to kick off the generation of an AI answer
    use_existing_user_message: bool = False

    @root_validator
    def check_search_doc_ids_or_retrieval_options(cls: BaseModel, values: dict) -> dict:
        search_doc_ids, retrieval_options = values.get("search_doc_ids"), values.get(
            "retrieval_options"
        )

        if search_doc_ids is None and retrieval_options is None:
            raise ValueError(
                "Either search_doc_ids or retrieval_options must be provided, but not both or neither."
            )

        return values


class ChatMessageIdentifier(BaseModel):
    message_id: int


class ChatRenameRequest(BaseModel):
    chat_session_id: int
    name: str | None = None


class ChatSessionUpdateRequest(BaseModel):
    sharing_status: ChatSessionSharedStatus


class RenameChatSessionResponse(BaseModel):
    new_name: str  # This is only really useful if the name is generated


class ChatSessionDetails(BaseModel):
    id: int
    name: str
    persona_id: int
    time_created: str
    shared_status: ChatSessionSharedStatus
    folder_id: int | None
    current_alternate_model: str | None = None


class ChatSessionsResponse(BaseModel):
    sessions: list[ChatSessionDetails]


class SearchFeedbackRequest(BaseModel):
    message_id: int
    document_id: str
    document_rank: int
    click: bool
    search_feedback: SearchFeedbackType | None

    @root_validator
    def check_click_or_search_feedback(cls: BaseModel, values: dict) -> dict:
        click, feedback = values.get("click"), values.get("search_feedback")

        if click is False and feedback is None:
            raise ValueError("Empty feedback received.")
        return values


class ChatMessageDetail(BaseModel):
    message_id: int
    parent_message: int | None
    latest_child_message: int | None
    message: str
    rephrased_query: str | None
    context_docs: RetrievalDocs | None
    message_type: MessageType
    time_sent: datetime
    alternate_assistant_id: str | None
    overridden_model: str | None
    # Dict mapping citation number to db_doc_id
    chat_session_id: int | None = None
    citations: dict[int, int] | None
    files: list[FileDescriptor]
    tool_calls: list[ToolCallFinalResult]

    def dict(self, *args: list, **kwargs: dict[str, Any]) -> dict[str, Any]:  # type: ignore
        initial_dict = super().dict(*args, **kwargs)  # type: ignore
        initial_dict["time_sent"] = self.time_sent.isoformat()
        return initial_dict


class SearchSessionDetailResponse(BaseModel):
    search_session_id: int
    description: str
    documents: list[SearchDoc]
    messages: list[ChatMessageDetail]


class ChatSessionDetailResponse(BaseModel):
    chat_session_id: int
    description: str
    persona_id: int
    persona_name: str
    messages: list[ChatMessageDetail]
    time_created: datetime
    shared_status: ChatSessionSharedStatus
    current_alternate_model: str | None


class QueryValidationResponse(BaseModel):
    reasoning: str
    answerable: bool


class AdminSearchRequest(BaseModel):
    query: str
    filters: BaseFilters


class AdminSearchResponse(BaseModel):
    documents: list[SearchDoc]


class DanswerAnswer(BaseModel):
    answer: str | None
