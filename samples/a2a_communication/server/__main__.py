import click
import uvicorn

from a2a.server.agent_execution import AgentExecutor
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import (
    DefaultRequestHandler,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    GetTaskRequest,
    GetTaskResponse,
    SendMessageRequest,
    SendMessageResponse,
)

from samples.a2a_communication.server.agent_executor import HelloWorldAgentExecutor

class A2ARequestHandler(DefaultRequestHandler):
    """A2A Request Handler for the A2A Repo Agent."""

    def __init__(
        self, agent_executor: AgentExecutor, task_store: InMemoryTaskStore
    ):
        super().__init__(agent_executor, task_store)

    async def on_get_task(
        self, request: GetTaskRequest, *args, **kwargs
    ) -> GetTaskResponse:
        return await super().on_get_task(request, *args, **kwargs)

    async def on_message_send(
        self, request: SendMessageRequest, *args, **kwargs
    ) -> SendMessageResponse:
        return await super().on_message_send(request, *args, **kwargs)


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=9999)
def main(host: str, port: int):
    """Start the weather Q&A agent server backed by HelloWorldAgentExecutor."""
    skill = AgentSkill(
        id='answer_weather_questions',
        name='Answer questions about the weather',
        description=(
            'The agent can answer simple questions about the weather '
            'for given locations using a weather tool.'
        ),
        tags=['weather', 'q&a'],
        examples=[
            'What is the weather in Amsterdam?',
            'What is the weather like in Paris and Berlin?',
        ],
    )

    agent_card = AgentCard(
        name='Weather Q&A Agent',
        description=(
            'A simple weather question answering agent that uses a tool '
            'to respond with current-like conditions for requested locations.'
        ),
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(
            input_modes=['text'],
            output_modes=['text'],
            # The current executor implementation performs a single-turn completion
            # and returns the final result, so we do not enable streaming here.
            streaming=False,
        ),
        skills=[skill],
        examples=[
            'What is the weather in Amsterdam?',
            'What is the weather like in Paris and Berlin?',
        ],
    )

    task_store = InMemoryTaskStore()
    request_handler = A2ARequestHandler(
        agent_executor=HelloWorldAgentExecutor(),
        task_store=task_store,
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    uvicorn.run(server.build(), host=host, port=port)


if __name__ == '__main__':
    main()