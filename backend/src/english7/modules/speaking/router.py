from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, UploadFile, File, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from english7.api.errors import ApplicationError
from english7.core.settings import get_settings
from english7.db.session import get_session_factory
from english7.modules.auth.domain import AuthUser
from english7.modules.quizzes.router import require_student
from english7.modules.speaking.repository import SpeakingRepository
from english7.modules.speaking.runtime import LocalSpeechRuntime
from english7.modules.speaking.service import SpeakingService, MAX_AUDIO_BYTES

router = APIRouter(tags=['learning'])
Student = Annotated[AuthUser, Depends(require_student)]


def get_speaking_service():
    from english7.modules.flashcards.router import create_flashcard_service
    settings = get_settings()
    return SpeakingService(SpeakingRepository(get_session_factory()), create_flashcard_service(),
                           LocalSpeechRuntime(settings.speech_runtime_url, settings.speech_timeout_seconds))


Service = Annotated[SpeakingService, Depends(get_speaking_service)]


class VoiceRequest(BaseModel):
    voice_id: str = Field(min_length=1, max_length=100)


@router.get('/speaking/voices')
def voices(user: Student, service: Service):
    return service.voices(user.id)


@router.put('/speaking/voice')
def set_voice(payload: VoiceRequest, user: Student, service: Service):
    return service.set_voice(user.id, payload.voice_id)


@router.post('/speaking/preview')
def preview(payload: VoiceRequest, user: Student, service: Service):
    return Response(service.preview(payload.voice_id), media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@router.post('/speaking/attempts/{request_id}')
async def submit(request_id: UUID, card_id: UUID, user: Student, service: Service,
                 voice_id: Annotated[str, Query(min_length=1, max_length=100)],
                 audio: Annotated[UploadFile, File()],
                 prompt: Annotated[str | None, Query(max_length=500)] = None):
    try:
        data = await audio.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise ApplicationError('recording_too_large', 'Recording exceeds 2 MiB', 413)
        return await run_in_threadpool(service.submit, user.id, request_id, card_id, voice_id, data, prompt=prompt)
    finally:
        await audio.close()


@router.post('/speaking/attempts/{attempt_id}/audio')
def audio(attempt_id: UUID, user: Student, service: Service):
    return Response(service.feedback_audio(user.id, attempt_id), media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@router.get('/speaking/history')
def history(user: Student, service: Service):
    return {'items': service.history(user.id)}


@router.get('/learning/progress')
def progress(user: Student, service: Service):
    return service.progress(user.id)
