from typing import AsyncIterable, Union
import asyncio
import typing
import google_a2a
from google_a2a.common.server.task_manager import InMemoryTaskManager
from my_project.agent import create_ollama_agent, run_ollama
from google_a2a.common.types import (
    Artifact,
    JSONRPCResponse,
    Message,
    SendTaskRequest,
    SendTaskResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
import logging

logger = logging.getLogger(__name__)

class MyAgentTaskManager(InMemoryTaskManager):
    def __init__(
        self,
        gemini_api: str,
        gemini_model: typing.Union[None, str]
    ):
        super().__init__()
        if gemini_model is not None:
            self.ollama_agent = create_ollama_agent(
                MODEL=gemini_model,
                GOOGLE_API_KEY=gemini_api
            )
        else:
            self.ollama_agent = None

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        # Upsert a task stored by InMemoryTaskManager
        await self.upsert_task(request.params)

        task_id = request.params.id
        # Our custom logic that simply marks the task as complete
        # and returns the echo text
        received_text = request.params.message.parts[0].text
        response_text = f"on_send_task received: {received_text}"
        if self.ollama_agent is not None:
            response_text = await run_ollama(ollama_agent=self.ollama_agent, prompt=received_text)
            
        task = await self._update_task(
            task_id=task_id,
            task_state=TaskState.COMPLETED,
            response_text=response_text  
        )

        # Send the response
        return SendTaskResponse(id=request.id, result=task)

    async def _stream_3_messages(self, request: SendTaskStreamingRequest):
        task_id = request.params.id
        received_text = request.params.message.parts[0].text

        text_messages = ["one", "two", "three"]
        for text in text_messages:
            parts = [
                {
                    "type": "text",
                    "text": f"{received_text}: {text}",
                }
            ]
            message = Message(role="agent", parts=parts)
            task_state = TaskState.WORKING
            task_status = TaskStatus(
                state=task_state,
                message=message
            )
            task_update_event = TaskStatusUpdateEvent(
                id=request.params.id,
                status=task_status,
                final=False,
            )
            await self.enqueue_events_for_sse(
                request.params.id,
                task_update_event
            )
        ask_message = Message(
            role="agent",
            parts=[
                {
                    "type": "text",
                    "text": "Would you like more messages? (Y/N)"
                }
            ]
        )
        task_update_event = TaskStatusUpdateEvent(
            id=request.params.id,
            status=TaskStatus(
                state=TaskState.INPUT_REQUIRED,
                message=ask_message
            ),
            final=True,
        )
        await self.enqueue_events_for_sse(
            request.params.id,
            task_update_event
        )
    
    async def on_send_task_subscribe(
        self,
        request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        task_id = request.params.id
        is_new_task = task_id not in self.tasks  # Fixed logic (was inverted)
        # Upsert a task stored by InMemoryTaskManager
        await self.upsert_task(request.params)

        received_text = request.params.message.parts[0].text
        sse_event_queue = await self.setup_sse_consumer(task_id=task_id)

        # -- PERUBAHAN --
        if self.ollama_agent is not None:
            logger.info(f"Task {task_id}: Handling with Gemini agent via streaming.")
            # Jalankan agent Gemini di background task agar tidak memblokir SSE
            async def run_agent_and_send_result():
                try:
                    # Panggil agent Gemini/LangGraph
                    response_text = await run_ollama(ollama_agent=self.ollama_agent, prompt=received_text)

                    # Kirim hasil akhir sebagai event SSE
                    task_update_event = TaskStatusUpdateEvent(
                        id=task_id,
                        status=TaskStatus(
                            state=TaskState.COMPLETED,
                            message=Message(
                                role="agent",
                                parts=[{"type": "text", "text": response_text}]
                            )
                        ),
                        final=True, # Tandai sebagai event terakhir
                    )
                    await self.enqueue_events_for_sse(task_id, task_update_event)
                    logger.info(f"Task {task_id}: Gemini response sent via SSE.")

                except Exception as e:
                    logger.error(f"Task {task_id}: Error running Gemini agent: {e}", exc_info=True)
                    # Kirim pesan error jika gagal
                    error_message = f"Error processing request: {e}"
                    task_update_event = TaskStatusUpdateEvent(
                        id=task_id,
                        status=TaskStatus(
                            state=TaskState.FAILED,
                            message=Message(
                                role="agent",
                                parts=[{"type": "text", "text": error_message}]
                            )
                        ),
                        final=True,
                    )
                    await self.enqueue_events_for_sse(task_id, task_update_event)

            # Jalankan di background
            asyncio.create_task(run_agent_and_send_result())

        else:
            # Fallback: Jika tidak ada agent Gemini, jalankan demo stream (atau berikan pesan error)
            logger.warning(f"Task {task_id}: Gemini agent not configured. Falling back to demo stream.")
            fallback_message = "Agent not configured to handle this request."
            task_update_event = TaskStatusUpdateEvent(
                id=task_id,
                status=TaskStatus(
                    state=TaskState.FAILED,
                    message=Message(
                        role="agent",
                        parts=[{"type": "text", "text": fallback_message}]
                    )
                ),
                final=True,
            )
            await self.enqueue_events_for_sse(task_id, task_update_event)

        # --- AKHIR PERUBAHAN ---

        # Tetap kembalikan generator SSE untuk mengirim event yang diantrekan
        # return self.dequeue_events_for_sse(
        #     request_id=request.id,
        #     task_id=task_id,
        #     sse_event_queue=sse_event_queue,
        # )

        # if not is_new_task and received_text == "N":
        #     task_update_event = TaskStatusUpdateEvent(
        #         id=request.params.id,
        #         status=TaskStatus(
        #             state=TaskState.COMPLETED,
        #             message=Message(
        #                 role="agent",
        #                 parts=[
        #                     {
        #                         "type": "text",
        #                         "text": "All done!"
        #                     }
        #                 ]
        #             )
        #         ),
        #         final=True,
        #     )
        #     await self.enqueue_events_for_sse(
        #         request.params.id,
        #         task_update_event,
        #     )
        # else:
        #     asyncio.create_task(self._stream_3_messages(request))

        # return self.dequeue_events_for_sse(
        #     request_id=request.id,
        #     task_id=task_id,
        #     sse_event_queue=sse_event_queue,
        # )

    async def _update_task(
        self,
        task_id: str,
        task_state: TaskState,
        response_text: str,
    ) -> Task:
        task = self.tasks[task_id]
        agent_response_parts = [
            {
                "type": "text",
                "text": response_text,
            }
        ]
        task.status = TaskStatus(
            state=task_state,
            message=Message(
                role="agent",
                parts=agent_response_parts,
            )
        )
        task.artifacts = [
            Artifact(
                parts=agent_response_parts,
            )
        ]
        return task